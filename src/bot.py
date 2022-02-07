from multiprocessing.sharedctypes import Value
import os
import sqlite3
import time
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import tweepy

load_dotenv()

CONSUMER_KEY=os.getenv('CONSUMER_KEY')
CONSUMER_SECRET=os.getenv('CONSUMER_SECRET')
ACCESS_TOKEN=os.getenv('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET=os.getenv('ACCESS_TOKEN_SECRET')
CONFIG_LANGUAGE = os.getenv('CONFIG_LANGUAGE').lower()
CONFIG_PERIOD = os.getenv('CONFIG_PERIOD').lower()
LOOP_PERIOD = int(os.getenv('LOOP_PERIOD'))

authentication_instance = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
authentication_instance.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
API_INSTANCE = tweepy.API(authentication_instance)

URL = f"https://github.com/trending/{CONFIG_LANGUAGE}?since={CONFIG_PERIOD}&spoken_language_code="

def has_tweeted(repo_data):
    organization = repo_data['organization']
    name = repo_data['name']

    conn = sqlite3.connect('src/repos.db')
    conn.execute("""
        CREATE TABLE IF NOT EXISTS
            repos (
                organization CHAR,
                name CHAR,
                timestamp INTEGER,
                PRIMARY KEY (organization, name, timestamp)
            )
    """)
    conn.execute("""CREATE INDEX IF NOT EXISTS repo_index ON repos (organization, name)""")

    repo_last_posted = conn.execute("""
        SELECT *
        FROM repos
        WHERE
            organization=? AND
            name=?
        ORDER BY
            timestamp DESC
    """, (organization, name)).fetchone()

    conn.execute(
        """INSERT INTO repos (organization, name, timestamp) VALUES (?, ?, ?)""",
        (organization, name, int(time.time()))
    )
    conn.commit()
    conn.close()

    if repo_last_posted:
        return repo_last_posted[2] + 86_400 > time.time()
    return False

def format_tweet(repo_data):
    (
        organization,
        name,
        description,
        repo_link,
        stars,
        star_gains,
    ) = repo_data.values()

    formatted_period = {
        'daily': 'today',
        'weekly': 'this week',
        'monthly': 'this month',
    }[CONFIG_PERIOD]

    return (
        f"{organization}/{name}\n"
        f"⭐{f'{stars:,}'} (+{f'{star_gains:,}'} {formatted_period})\n\n"
        f"{description[:(245 - len(organization) - len(name) - len(repo_link))]}\n"
        f"{repo_link}"
    )

def scrape_repo_data(soup):
    a_elements = soup.select('a[href]')

    repo = a_elements[1].get('href')[1:].split('/')
    organization = repo[0]
    name = repo[1]
    description = ' '.join([e.text for e in soup.select('p')]).strip()
    stars = 0
    for a_element in a_elements:
        if len(a_element.select('svg[class*="octicon-star"]')) > 0:
            try:
                stars = int(a_element.text.strip().replace(',', ''))
            except ValueError:
                continue
            break
    try:
        star_gains = int(soup.select('span')[-1].text.strip().split(' ')[0].replace(',', ''))
    except ValueError:
        star_gains = 0

    return {
        'organization': organization,
        'name': name,
        'description': description,
        'repo_link': f"https://github.com/{organization}/{name}",
        'stars': stars,
        'star_gains': star_gains,
    }

async def scrape_repos():
    async with aiohttp.ClientSession() as session:
        async with session.get(url=URL) as response:
            soup = BeautifulSoup(await response.read(), 'html.parser')

    repos = soup.find_all('article')
    return [scrape_repo_data(repo) for repo in repos if repo]

async def post_tweet(tweet):
    API_INSTANCE.update_status(status=tweet)

async def main():
    trending_repos = await scrape_repos()
    for repo_data in trending_repos:
        if has_tweeted(repo_data): continue
        await post_tweet(format_tweet(repo_data))
        await asyncio.sleep(10)

if __name__ == '__main__':
    print('RUNNING')
    asyncio.run(main())
