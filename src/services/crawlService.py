import sqlite3
from uuid import uuid4

from constants import crawl as CrawlConstants
from httpx import AsyncClient, AsyncHTTPTransport


class CrawlService:
    def __init__(self):
        # httpx AsyncHTTPTransport 초기화
        self.transport = AsyncHTTPTransport(retries=1)

        # 유저의 게시물 링크를 저장할 DB
        self.db_conn = sqlite3.connect("../database/posted_link.db")
    async def checkForNewPosts(self, max_page: int):
        if not self.transport:
            raise Exception("httpx AsyncHTTPTransport is not initialised or destoryed.")

        # region DB 초기화
        db_cur = self.db_conn.cursor()
        db_cur.execute("CREATE TABLE IF NOT EXISTS posted_link (link TEXT, title TEXT)")
        self.db_conn.commit()
        # endregion

        # region 이미 포스트한 게시물 링크 가져오기
        db_cur.execute("SELECT * FROM posted_link")
        posted_link = db_cur.fetchall()
        # endregion

        return_data = []

        async with AsyncClient(transport=self.transport) as client:
            # region 네이버 카페 게시물 가져오기
            response = await client.get(
                CrawlConstants.NAVER_CAFE_ARTICLE_API
                + f"?search.clubid={CrawlConstants.NAVER_CAFE_CLUBID}"
                + f"&search.menuid={CrawlConstants.NAVER_CAFE_MENUID}"
                + "&search.queryType=lastArticle"
                + f"&search.page=1&search.perPage={max_page}"
                + f"&uuid={uuid4()}"
                + "&ad=false&adUnit=MW_CAFE_ARTICLE_LIST_RS",
            )

            response.raise_for_status()

            # 게시물 리스트 중에서 반응정리 팀의 게시물을 찾음
            article_list = []
            for article in response.json()["message"]["result"]["articleList"]:
                if article["memberKey"] == CrawlConstants.NAVER_CAFE_REACTION_MEMBERKEY:
                    article_list.append(article)
            # endregion

            # region DB에 저장
            for article in article_list[::-1]:

                url = f"https://cafe.naver.com/steamindiegame/{article['articleId']}"

                if not any(url in link for link in posted_link):
                    db_cur.execute(
                        "INSERT INTO posted_link (link, title) VALUES (?, ?)",
                        (url, str(article["subject"])),
                    )
                    self.db_conn.commit()
            # endregion
