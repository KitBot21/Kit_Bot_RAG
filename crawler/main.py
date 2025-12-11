import sys
from setting.loader import Loader
from core.crawl import Crawler

def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config_ko.yml"
    s = Loader.from_yaml(cfg_path)
    Crawler(s).run()

if __name__ == "__main__":
    main()