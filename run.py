"""toronto-open-poi -- pull the feeds, classify them against OSM, explore the result.

    python run.py fetch [--force]   download the feeds, the archive and the OSM extracts
    python run.py build             classify and render site/explorer/
    python run.py serve [--port N]  serve site/ and open the explorer
    python run.py all               fetch, build, serve
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading
import webbrowser

from src import config


def cmd_fetch(args):
    from src import fetch
    fetch.fetch(force=args.force)


def cmd_build(args):
    from src import classify, reduce, site
    records, gaz = reduce.establishments()
    print('%s establishments reduced from both feeds' % '{:,}'.format(len(records)))
    records, orphans = classify.classify(records, gaz)
    site.build(records, orphans)


def cmd_serve(args):
    root = config.SITE_DIR
    if not os.path.isdir(os.path.join(root, 'explorer')):
        sys.exit("nothing built yet -- run 'python run.py build' first")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root, **kw)

        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', args.port), Handler) as httpd:
        url = 'http://127.0.0.1:%d/explorer/' % args.port
        print('serving %s at %s  (ctrl-c to stop)' % (root, url))
        if not args.no_open:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('fetch', help='download the feeds and OSM extracts')
    p.add_argument('--force', action='store_true', help='re-download what is already on disk')
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser('build', help='classify and render the explorer')
    p.set_defaults(func=cmd_build)

    p = sub.add_parser('serve', help='serve site/ and open the explorer')
    p.add_argument('--port', type=int, default=8777)
    p.add_argument('--no-open', action='store_true')
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser('all', help='fetch, build, then serve')
    p.add_argument('--force', action='store_true')
    p.add_argument('--port', type=int, default=8777)
    p.add_argument('--no-open', action='store_true')
    p.set_defaults(func=lambda a: (cmd_fetch(a), cmd_build(a), cmd_serve(a)))

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
