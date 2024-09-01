import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import threading
from PIL import Image
from fpdf import FPDF
from PyPDF2 import PdfMerger
import shutil
import time
import re


DIR = os.getcwd()+"//manga"
if not os.path.exists(DIR):
    os.mkdir(DIR)

# Function to fetch chapter links from the main manga page
def chapter_links(URL) -> dict:
    retry_attempts = 5
    for attempt in range(retry_attempts):
        try:
            r = requests.get(URL)
            soup = BeautifulSoup(r.content, 'html.parser')
            chapters = soup.find_all("a", {"class": "chapter-name text-nowrap"})
            links = {chapter.text.strip(): chapter['href'] for chapter in chapters}
            return links
        except requests.exceptions.RequestException as e:
            print(f"Error fetching chapter links: {e}")
            if attempt < retry_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                raise

# Function to get image URLs for a specific chapter
def page_links(url) -> list:
    retry_attempts = 5
    for attempt in range(retry_attempts):
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, 'html.parser')
            div = str(soup.find("div", {"class": "container-chapter-reader"}))
            imgs = BeautifulSoup(div, 'html.parser').find_all("img")
            page_urls = [i['src'] for i in imgs]
            return page_urls
        except requests.exceptions.RequestException as e:
            print(f"Error fetching page links: {e}")
            if attempt < retry_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                raise

def download_image(name, url):
        retry_attempts = 5
        for attempt in range(retry_attempts):
            try:
                domain = urllib.parse.urlparse(url).netloc
                HEADERS = {
                    'Accept': 'image/png,image/svg+xml,image/*;q=0.8,video/*;q=0.8,*/*;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.2 Safari/605.1.15',
                    'Host': domain, 'Accept-Language': 'en-ca', 'Referer': 'https://chapmanganato.to/',
                    'Connection': 'keep-alive'
                }
                r = requests.get(url, headers=HEADERS, stream=True)
                if r.status_code != 200:
                    raise Exception(f"HTTP error: {r.status_code}")
                
                content_type = r.headers.get('Content-Type')
                if not content_type or 'image' not in content_type:
                    raise Exception(f"Invalid content type: {content_type}")

                
                with open(name, 'wb') as f:
                    f.write(r.content)

                with Image.open(name) as img:
                    img.verify()


                input_image = Image.open(name).convert("RGBA")
                image = Image.new("RGB", input_image.size, "WHITE")
                image.paste(input_image, (0, 0), input_image)
                os.remove(name)
                image.save(name)
                break
            except (requests.exceptions.RequestException, Exception) as e:
                print(f"Error downloading image {name} from {url}: {e}")
                if os.path.exists(name):
                    os.remove(name)
                if attempt < retry_attempts - 1:
                    time.sleep(2 ** attempt)
                else:
                    # Save error response for analysis
                    error_filename = f"error_{name}.html"
                    with open(error_filename, 'wb') as f:
                        f.write(r.content)
                    print(f"Saved error response content to {error_filename}")

# Function to download all images using threading
def download_all_images(urls):
    threads = []
    for i in range(len(urls)):
        t = threading.Thread(target=download_image, args=(str(i + 1) + ".jpg", urls[i]))
        threads.append(t)
        t.start()
    for thread in threads:
        thread.join()

# Function to convert downloaded images into a PDF
def convert_to_pdf(name, path, imgs, pdfs):
    try:
        merger = PdfMerger()
        for i, img in enumerate(imgs):
            with Image.open(img) as cover:
                width, height = cover.size
                width, height = float(width * 0.264583), float(height * 0.264583)
                pdf = FPDF("P", "mm", (width, height))
                pdf.add_page()
                pdf.image(img, 0, 0, width, height)
                pdf.output(pdfs[i], "F")
                

            # Explicitly close the image file before trying to remove it
            cover.close()
            # Wait before removing the file to ensure it's fully released
            try:
                os.remove(img)
            except PermissionError:
                print(f"Permission error when deleting {img}. Retrying...")
                cover.close()

        # Merge PDFs after all images have been converted
        for pdf in pdfs:
            merger.append(pdf)

        # Save the final merged PDF
        merged_pdf_path = os.path.join(DIR, f"{name}.pdf")
        merger.write(merged_pdf_path)
        merger.close()

        # Clean up the PDFs after merging
        # for pdf in pdfs:
        #     try:
        #         os.remove(pdf)
        #     except Exception as e:
        #         print(f"Error removing temporary PDF {pdf}: {e}")

        # Clean up the directory
        os.chdir(DIR)
        shutil.rmtree(path)
        print(f"Downloaded {name} Successfully")

    except Exception as e:
        print(f"Error converting images to PDF: {e}")


# Function to download manga chapters and convert them to PDFs
def download_manga(name, url):
    name = ''.join(char for char in name if char.isalnum() or char.isspace())
    print(f"Downloading {name} from {url}")
    pages = page_links(url)
    num = len(pages)
    print(f"Downloading {num} pages")
    path = os.path.join(DIR, name)
    if not os.path.exists(path):
        os.mkdir(path)
    os.chdir(path)
    download_all_images(pages)
    imgs = [f"{i + 1}.jpg" for i in range(num)]
    pdfs = [f"{i + 1}.pdf" for i in range(num)]
    convert_to_pdf(name, path, imgs, pdfs)


def sort_chapters(chapters):
    def extract_chapter_number(chapter_name):
        # Extracting chapter number considering possible decimal points
        match = re.search(r'Chapter (\d+(?:\.\d+)?)', chapter_name)
        return float(match.group(1)) if match else float('inf')

    sorted_chapters = dict(sorted(chapters.items(), key=lambda x: extract_chapter_number(x[0])))
    return sorted_chapters

# Main function to run the script
def main():
    manga_id = input("Enter the manga id: ").strip()
    manga_url = f"https://chapmanganato.to/manga-{manga_id}/"
    chapters = chapter_links(manga_url)
    chapters = sort_chapters(chapters)

    while True:
        print("Choose an option:")
        print("1. Download all chapters at once")
        print("2. Download chapters sequentially")
        print("3. Download a particular chapter")
        print("4. Quit (q)")

        choice = input("Enter your choice (1/2/3/4): ")

        if choice == '1':
            for chapter in chapters:
                download_manga(chapter, chapters[chapter])
        elif choice == '2':
            for chapter in chapters:
                print(chapter + ": " + chapters[chapter])
                y = input("Download? (Y/n/q): ")
                if y.lower() == 'y':
                    download_manga(chapter, chapters[chapter])
                elif y.lower() == 'q':
                    print("Exiting...")
                    return
        elif choice == '3':
            print("Available chapters:")
            for chapter in chapters:
                print(chapter + ": " + chapters[chapter])
            chap_name = input("Enter the name of the chapter to download: ")
            if chap_name in chapters:
                download_manga(chap_name, chapters[chap_name])
            else:
                print("Chapter not found.")
        elif choice.lower() == '4' or choice.lower() == 'q':
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()
