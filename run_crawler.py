import subprocess
import sys

def main():
    category_urls = [
        "https://tiki.vn/dien-thoai-smartphone/c1795",
        "https://tiki.vn/laptop/c8095",
        "https://tiki.vn/tivi/c4221"
    ]
    
    command = [
        sys.executable, "-m", "src.crawler.tiki_crawler",
        "--category-urls", ",".join(category_urls),
        "--max-products-per-category", "50"
    ]
    
    print("Starting crawler...")
    try:
        subprocess.run(command, check=True)
        print("\nCrawler finished successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\nCrawler failed with exit code: {e.returncode}")
    except KeyboardInterrupt:
        print("\nCrawler stopped by user.")

if __name__ == "__main__":
    main()
