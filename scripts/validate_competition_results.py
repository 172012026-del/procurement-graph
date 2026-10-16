"""Run format and source-fact acceptance checks without model calls."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--dataset',required=True)
    parser.add_argument('--workbook',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--relationships',type=Path)
    args = parser.parse_args()
    os.environ['DATABASE_PATH'] = str(args.database.resolve())
    sys.path.insert(0,str(ROOT/'demo/procurement/backend'))
    from app.acceptance import check_relationships, check_workbook
    ids = {p.stem for p in (ROOT/'data/official-benchmark/html').glob('*.html')}
    report = {'workbook':check_workbook(args.workbook.read_bytes(),ROOT/'data/official-benchmark/indexes/output-schema.json',ids)}
    if args.relationships:
        report['relationships'] = check_relationships(args.relationships,args.dataset)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'workbook_valid':report['workbook']['valid'],
        'required_blue_positions':report['workbook']['required_blue_positions'],
        'relationships_passed':report.get('relationships',{}).get('passed'),
        'source_fact_errors':len(report.get('relationships',{}).get('fact_errors',[]))}))


if __name__=='__main__':
    main()
