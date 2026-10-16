"""Local-only supervised LoRA training. Requires approved train/validation data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def read_data(path: Path):
    data = [json.loads(line) for line in path.read_text('utf-8').splitlines() if line.strip()]
    if not data or any(row.get('reviewed') is not True for row in data):
        raise ValueError('Training requires nonempty, human-reviewed data; draft predictions are not accepted')
    for row in data:
        if [message['role'] for message in row.get('messages',[])] != ['system','user','assistant']:
            raise ValueError('Expected system/user/assistant messages')
        target = json.loads(row['messages'][-1]['content'])
        fingerprint = hashlib.sha256(json.dumps(target,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        if fingerprint != row.get('target_sha256'):
            raise ValueError('Reviewed target changed after approval')
    return data


def validate(train, validation):
    first = {row['notice_uuid'] for row in train}
    second = {row['notice_uuid'] for row in validation}
    if first & second:
        raise ValueError('A notice cannot appear in both train and validation')
    sources_train = {row['source_sha256'] for row in train}
    if sources_train & {row['source_sha256'] for row in validation}:
        raise ValueError('Identical source content cannot cross the train/validation boundary')
    if len(first) != len(train) or len(second) != len(validation):
        raise ValueError('Duplicate notice in one split')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--base-model', type=Path)
    parser.add_argument('--model-profile', type=Path)
    parser.add_argument('--output', type=Path, default=Path('results/lora-adapter'))
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--max-length', type=int, default=8192)
    parser.add_argument('--epochs', type=float, default=2)
    args = parser.parse_args()
    train, validation = read_data(args.data/'train.jsonl'), read_data(args.data/'validation.jsonl')
    validate(train,validation)
    if args.validate_only:
        print(json.dumps({'passed':True,'train':len(train),'validation':len(validation),'training_executed':False}))
        return
    if not args.base_model or not args.base_model.is_dir() or not args.model_profile or not args.model_profile.is_file():
        parser.error('A local model directory and its model-profile JSON are required')
    metadata = json.loads(args.model_profile.read_text('utf-8'))
    if not all(metadata.get(key) for key in ['model_id','version','parameter_scale']) or not (metadata.get('resource_evidence') or metadata.get('organizer_evidence')):
        parser.error('Complete the model identity and source evidence before training')
    # Loading never falls back to downloading a model or remote custom Python code.
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments, set_seed
    set_seed(2026)
    if not torch.cuda.is_available():
        parser.error('CUDA is required for this training recipe; validation-only works without GPU dependencies')
    tokenizer = AutoTokenizer.from_pretrained(args.base_model,local_files_only=True,trust_remote_code=False)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    def encode(records):
        encoded=[]
        for row in records:
            prompt=tokenizer.apply_chat_template(row['messages'][:-1],tokenize=False,add_generation_prompt=True)
            prefix=tokenizer(prompt,add_special_tokens=False)['input_ids']
            answer=tokenizer(row['messages'][-1]['content']+tokenizer.eos_token,add_special_tokens=False)['input_ids']
            if len(prefix)+len(answer)>args.max_length:
                raise ValueError('Example exceeds max length; split and review it instead of truncating labels: '+row['notice_uuid'])
            encoded.append({'input_ids':prefix+answer,'labels':[-100]*len(prefix)+answer})
        return encoded
    train_data, validation_data = encode(train),encode(validation)
    def collate(examples):
        length=max(len(row['input_ids']) for row in examples)
        return {'input_ids':torch.tensor([row['input_ids']+[tokenizer.pad_token_id]*(length-len(row['input_ids'])) for row in examples]),
                'attention_mask':torch.tensor([[1]*len(row['input_ids'])+[0]*(length-len(row['input_ids'])) for row in examples]),
                'labels':torch.tensor([row['labels']+[-100]*(length-len(row['labels'])) for row in examples])}
    bf16 = torch.cuda.is_bf16_supported()
    model=AutoModelForCausalLM.from_pretrained(args.base_model,local_files_only=True,trust_remote_code=False,
                                            torch_dtype=torch.bfloat16 if bf16 else torch.float16)
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=.05,target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
    model.config.use_cache=False
    options=TrainingArguments(output_dir=str(args.output),num_train_epochs=args.epochs,per_device_train_batch_size=1,
        per_device_eval_batch_size=1,gradient_accumulation_steps=8,learning_rate=2e-4,eval_strategy='epoch',save_strategy='epoch',
        logging_steps=5,save_total_limit=2,bf16=bf16,fp16=not bf16,report_to=[],seed=2026,remove_unused_columns=False)
    trainer=Trainer(model=model,args=options,train_dataset=train_data,eval_dataset=validation_data,data_collator=collate)
    trainer.train()
    trainer.save_model(str(args.output));tokenizer.save_pretrained(args.output)
    (args.output/'model-profile.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.output/'metrics.json').write_text(json.dumps(trainer.evaluate(),indent=2),encoding='utf-8')
    print(json.dumps({'adapter_saved':str(args.output),'training_executed':True,'model_downloads':0}))


if __name__ == '__main__':
    main()
