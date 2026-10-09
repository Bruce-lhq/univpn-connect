"""Entry point usable from source and frozen desktop/CLI packages."""
import sys
from pathlib import Path
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--service':
        sys.argv.pop(1)
        from univpn_client.daemon import main as run
    elif len(sys.argv)>1 and sys.argv[1]=='--helper':
        sys.argv.pop(1)
        from univpn_client.helper import main as run
    elif len(sys.argv)>1 and sys.argv[1]=='--route-hook':
        from univpn_client.routes import route_hook
        return route_hook()
    elif len(sys.argv)==1:
        from univpn_client.desktop import main as run
    else:
        from univpn_client.cli import main as run
    return run()

if __name__=='__main__':raise SystemExit(main())
