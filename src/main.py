import os
import tkinter as tk
import asyncio

from tkinter import ttk

from services.crawlService import CrawlService
#from tests import DownloadAudio
if __name__ == "__main__":
    # Main()

    async def main():
        crawlService = CrawlService()
        await crawlService.checkForNewPosts(30)

    asyncio.run(main())
