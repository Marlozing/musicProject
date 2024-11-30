import asyncio
import sqlite3

from services.crawlService import CrawlService

# from tests import DownloadAudio
if __name__ == "__main__":
    # Main()

    async def main():
        crawlService = CrawlService()
        await crawlService.checkForNewPosts(50)

    asyncio.run(main())
