"""CLI wrapper for graph synchronization; no model calls."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'demo/procurement/backend'))
from app.graph_cli import main
if __name__=='__main__':
    main()
