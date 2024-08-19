import asyncio
import logging
from datetime import datetime
from collections import defaultdict

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from rest_framework import status, viewsets
from rest_framework.response import Response

logging.basicConfig(level=logging.INFO)

class ScrapeViewSet(viewsets.ViewSet):
    async def scrape(self):
        base_url = 'https://crossword-solver.io'

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', args=['--no-sandbox'])
            page = await browser.new_page()
            results = defaultdict(list)

            try:
                await page.goto(base_url, timeout=None)
                await page.wait_for_selector('div[data-testid="todays-featured-puzzles-section"]', timeout=None)
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                target_section = soup.find('div', {'data-testid': 'todays-featured-puzzles-section'})
                urls = []

                # Extract URLs from the initial page
                if target_section:
                    crossword_data = target_section.find_all('div', class_='flex justify-between gap-2 items-center border-b border-b-gainsboro py-3 lg:py-3.5 lg:w-[288px] xl:w-[368px] 2xl:w-[448px]')
                    for entry in crossword_data:
                        category_anchor = entry.find('a', class_="text-lg lg:truncate hover:underline active:underline")
                        if category_anchor:
                            url_anchor = category_anchor['href']
                            category = category_anchor.text.strip()
                            full_url = f"{base_url}{url_anchor}" if url_anchor.startswith('/') else url_anchor
                            urls.append((full_url, category))
                            logging.info(f"Found URL: {full_url}")

                try:
                    # Extract href from "More Today's Puzzles" button
                    more_puzzles_link = soup.find('a', class_="rounded bg-washed-black text-white font-bold w-full text-center lg:px-6 py-3.5 lg:w-auto hover:bg-eerie-black active:bg-eerie-black")
                    if more_puzzles_link:
                        more_puzzles_url = more_puzzles_link['href']
                        full_more_puzzles_url = f"{base_url}{more_puzzles_url}" if more_puzzles_url.startswith('/') else more_puzzles_url
                        logging.info(f"Found More Today's Puzzles URL: {full_more_puzzles_url}")
                        await page.goto(full_more_puzzles_url, timeout=None)
                        await page.wait_for_selector('section[data-testid="discover-more-puzzles"]', timeout=None)
                        content = await page.content()
                        soup = BeautifulSoup(content, 'html.parser')
                        target_section = soup.find('section', {'data-testid': 'discover-more-puzzles'})

                        # Extract URLs from the new page
                        if target_section:
                            crossword_data = target_section.find_all('div', class_='flex justify-between gap-x-2 items-center border-b border-b-supreme-green py-3 lg:w-[288px] xl:w-[352px]')
                            for entry in crossword_data:
                                category_anchor = entry.find('a', class_="text-lg lg:truncate hover:underline active:underline")
                                if category_anchor:
                                    url_anchor = category_anchor['href']
                                    category = category_anchor.text.strip()
                                    full_url = f"{base_url}{url_anchor}" if url_anchor.startswith('/') else url_anchor
                                    urls.append((full_url, category))
                                    logging.info(f"Found URL: {full_url}")
                except Exception as e:
                    logging.error(f"Error processing 'More Today's Puzzles' button: {e}")

                # Function to get all pages from pagination
                async def get_all_pages(page, base_url, start_url):
                    page_urls = [start_url]
                    await page.goto(start_url, timeout=None)
                    while True:
                        await page.wait_for_selector('div.pagination', timeout=None)
                        content = await page.content()
                        soup = BeautifulSoup(content, 'html.parser')
                        pagination = soup.find('div', class_='pagination')
                        if not pagination:
                            break
                        next_page_link = pagination.find('a', rel='next nofollow')
                        if next_page_link and 'href' in next_page_link.attrs:
                            next_page_url = next_page_link['href']
                            full_next_page_url = f"{base_url}{next_page_url}" if next_page_url.startswith('/') else next_page_url
                            page_urls.append(full_next_page_url)
                            logging.info(f"Found pagination URL: {full_next_page_url}")
                            await page.goto(full_next_page_url, timeout=None)
                        else:
                            break
                    return page_urls

                # Collect all pagination URLs for the specific crossword category
                specific_url = "https://crossword-solver.io/crossword-answers/times-specialist/"
                all_clue_urls = []
                for url, category in urls:
                    if url == specific_url:
                        try:
                            logging.info(f"Processing category URL: {url}")
                            page_urls = await get_all_pages(page, base_url, url)
                            for page_url in page_urls:
                                await page.goto(page_url, timeout=None)
                                await page.wait_for_selector('ul.list-group.list-group-flush', timeout=None)
                                content = await page.content()
                                soup = BeautifulSoup(content, 'html.parser')
                                clues_section = soup.find('ul', class_='list-group list-group-flush')
                                if clues_section:
                                    clues = clues_section.find_all('li', class_='list-group-item text-center h4')
                                    logging.info(f"Found clues section on page: {page_url}")
                                    clue_urls = [clue.find('a')['href'] for clue in clues]
                                    all_clue_urls.extend(clue_urls)
                                    logging.info(f"Clue URLs: {clue_urls}")
                        except Exception as e:
                            logging.error(f"Error processing URL {url}: {e}")
                            continue

                # Process each clue URL
                for clue_url in all_clue_urls:  # Limiting to the first clue URL for simplicity
                    try:
                        logging.info(f"We are navigating to clue URL: {clue_url}")
                        await page.goto(clue_url, timeout=None)
                        await page.wait_for_selector('div.card > div.card-body > ul.list-group.list-group-flush', timeout=None)
                        clues_section = await page.content()
                        clues_soup = BeautifulSoup(clues_section, 'html.parser')
                        clues_ul = clues_soup.find('div', class_='card').find('div', class_='card-body').find('ul', class_='list-group list-group-flush')
                        if clues_ul:
                            individual_clue_urls = [li.find('a')['href'] for li in clues_ul.find_all('li', class_='list-group-item h6')]
                            logging.info(f"Individual Clue URLs: {individual_clue_urls}")

                            # Process each individual clue URL
                            for individual_clue_url in individual_clue_urls:
                                try:
                                    logging.info(f"We are navigating to individual clue URL: {individual_clue_url}")
                                    await page.goto(individual_clue_url, timeout=60000)
                                    await page.wait_for_selector('div.reveal-btn', timeout=None)
                                    await page.click('div.reveal-btn button')
                                    await page.wait_for_selector('div.reveal-answer', timeout=None)

                                    # Extract content from individual clue URL
                                    individual_clue_content = await page.content()
                                    individual_clue_soup = BeautifulSoup(individual_clue_content, 'html.parser')

                                    # Extract title
                                    title_div = individual_clue_soup.find('div', class_='lg:row-span-2 max-w-full min-w-0 overflow-hidden')
                                    title = ""
                                    if title_div:
                                        title_h1 = title_div.find('h1', class_='text-[26px] leading-8 lg:text-[2rem] lg:leading-10 flex flex-col items-center lg:items-start gap-1 lg:block')
                                        if title_h1:
                                            title_b = title_h1.find('b')
                                            title = title_b.text.strip() if title_b else "No title found"

                                    # Extract category and date
                                    category_date_div = individual_clue_soup.find('div', class_='flex flex-col lg:flex-row mt-5 lg:mt-6 text-lg/6 items-center lg:items-start w-full')
                                    category = ""
                                    date = ""
                                    if category_date_div:
                                        category_anchor = category_date_div.find_all('a', class_='text-calypso hover:text-cws-blue-350 underline')
                                        if category_anchor:
                                            category = category_anchor[0].text.strip()
                                            if len(category_anchor) > 1:
                                                date = category_anchor[1].text.strip()

                                    # Extract answer
                                    answer_div = individual_clue_soup.find('div', class_='reveal-answer p-4 lg:pr-0 rounded-t-lg lg:rounded-tr-none lg:rounded-l-lg bg-cws-blue-400 border border-b-0 lg:border-b lg:border-r-0 border-cws-black-700 svelte-k8z3m2')
                                    answer_text = ""
                                    if answer_div:
                                        answer_text = ''.join([btn['data-letter'] for btn in answer_div.find_all('button', class_='svelte-mr6mw5')])

                                    # Click "Show More Answers" button until all answers are revealed
                                    while True:
                                        show_more_button = await page.query_selector('button[data-event="ShowLessAnswers"]')
                                        if show_more_button:
                                            logging.info(f"Clicking 'Show More Answers' button at {individual_clue_url}")
                                            await show_more_button.click()
                                            await page.wait_for_timeout(2000)  # Wait for content to load
                                        else:
                                            break

                                    # Extract potential answers
                                    individual_clue_content = await page.content()  # Reload the content
                                    individual_clue_soup = BeautifulSoup(individual_clue_content, 'html.parser')
                                    potential_answers_section = individual_clue_soup.find('section', class_='mt-2 lg:mt-4')
                                    potential_answers = []
                                    if potential_answers_section:
                                        for row in potential_answers_section.select('tbody tr'):
                                            answer = row.select_one('a').get_text(strip=True)
                                            percentage_element = row.select_one('td[data-testid^="clue-rank-"] span')
                                            percentage = percentage_element.get_text(strip=True) if percentage_element else ''
                                            clue_text_element = row.find('span', class_='text-base text-seared-grey clue-text svelte-1xq1aie')
                                            clue_text = clue_text_element.get_text(strip=True) if clue_text_element else ''
                                            potential_answers.append({
                                                'answer': answer,
                                                'percentage': percentage,
                                                'title': clue_text
                                            })

                                    logging.info(f"Found individual clue: {individual_clue_url}, title: {title}, category: {category}, date: {date}, answer: {answer_text}, potential answers: {potential_answers}")
                                    results[category].append({
                                        'title': title,
                                        'date': date,
                                        'answer': answer_text,
                                        'potential_answers': potential_answers
                                    })
                                except Exception as e:
                                    logging.error(f"Error accessing individual clue URL {individual_clue_url}: {e}")
                                    continue
                    except Exception as e:
                        logging.error(f"Error accessing clue URL {clue_url}: {e}")
                        continue

            except Exception as e:
                logging.error(f"Error accessing base URL: {e}")
            finally:
                await browser.close()

            formatted_results = [{'category': category, 'content': contents} for category, contents in results.items()]
            return {'results': formatted_results}, status.HTTP_200_OK

    def list(self, request):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results, status_code = loop.run_until_complete(self.scrape())
        return Response(results, status=status_code)
