import os
import sqlite3

from uuid import uuid4
from httpx import AsyncClient, AsyncHTTPTransport
from dotenv import load_dotenv

class CrawlService:
    # region 초기 설정
    def __init__(self):
        # httpx AsyncHTTPTransport 초기화
        self.transport = AsyncHTTPTransport(retries=1)

        # 유저의 게시물 링크를 저장할 DB
        self.db_conn = sqlite3.connect("./database/posted_link.db")
        db_cur = self.db_conn.cursor()
        db_cur.execute("CREATE TABLE IF NOT EXISTS posted_link (link TEXT, title TEXT)")
        self.db_conn.commit()

        load_dotenv("crawl.env")
    # endregion

    # region 게시물 찾기
    def find_article(self, response):
        article_list = []
        for article in response.json()["message"]["result"]["articleList"]:
            if article["memberKey"] == os.getenv("NAVER_CAFE_REACTION_MEMBERKEY"):
                article_list.append({"articleId": article["articleId"], "subject": article["subject"]})
        return article_list
    # endregion

    # region DB에 게시물 저장
    def save_db(self, article_list):
        db_cur = self.db_conn.cursor()

        for article in article_list[::-1]:
            article_id = article['articleId']

            # 링크가 이미 존재하는지 확인
            db_cur.execute("SELECT title FROM posted_link WHERE link = ?", (article_id,))
            existing_title = db_cur.fetchone()

            if existing_title is None:
                # 링크가 존재하지 않을 경우, 새로 삽입
                db_cur.execute(
                    "INSERT INTO posted_link (link, title) VALUES (?, ?)",
                    (article_id, str(article["subject"])),
                )
            elif existing_title[0] != str(article["subject"]):
                # 링크가 존재할 경우, 제목이 변경되었는지 확인
                db_cur.execute(
                    "UPDATE posted_link SET title = ? WHERE link = ?",
                    (str(article["subject"]), article_id),
                )
        self.db_conn.commit()
    # endregion

    # region 게시물 크롤링
    async def check_new_posts(self, max_page: int):
        if not self.transport:
            raise Exception("httpx AsyncHTTPTransport is not initialised or destoryed.")

        async with (AsyncClient(transport=self.transport) as client):

            # region 네이버 카페 게시물 가져오기
            response = await client.get(
                os.getenv("NAVER_CAFE_ARTICLE_API")
                + f"?search.clubid={os.getenv('NAVER_CAFE_CLUBID')}"
                + f"&search.menuid={os.getenv('NAVER_CAFE_MENUID')}"
                + "&search.queryType=lastArticle"
                + f"&search.page=1&search.perPage={max_page}"
                + f"&uuid={uuid4()}"
                + "&ad=false&adUnit=MW_CAFE_ARTICLE_LIST_RS",
            )

            response.raise_for_status()
            # endregion

            article_list = self.find_article(response)
            self.save_db(article_list)
    # endregion

    # region 최근 게시물 전부 크롤링
    async def crawl_until_known(self):
        if not self.transport:
            raise Exception("httpx AsyncHTTPTransport is not initialised or destoryed.")

        # region DB 점검
        db_cur = self.db_conn.cursor()

        db_cur.execute("SELECT COUNT(*) FROM posted_link")
        if (db_cur.fetchone() or (0,))[0] == 0:
            await self.check_new_posts(100)
            return
        # endregion

        # region 기존 데이터 가져오기
        db_cur.execute("SELECT link FROM posted_link ORDER BY link DESC LIMIT 1")
        existing_id = db_cur.fetchone()[0]
        self.db_conn.commit()
        # endregion

        # region 페이지 루프
        total_article_list = []
        page = 1

        async with AsyncClient(transport=self.transport) as client:
            while True:
                # region 네이버 카페 게시물 가져오기
                response = await client.get(
                    os.getenv("NAVER_CAFE_ARTICLE_API")
                    + f"?search.clubid={os.getenv('NAVER_CAFE_CLUBID')}"
                    + f"&search.menuid={os.getenv('NAVER_CAFE_MENUID')}"
                    + "&search.queryType=lastArticle"
                    + f"&search.page={page}&search.perPage=10"
                    + f"&uuid={uuid4()}"
                    + "&ad=false&adUnit=MW_CAFE_ARTICLE_LIST_RS",
                )

                response.raise_for_status()

                # 게시물 리스트 중에서 반응정리 팀의 게시물을 찾음
                article_list = self.find_article(response)

                # endregion

                # DB에 저장된 게시물이 포함되어있을 경우 종료
                if int(existing_id) >= int(min([a['articleId'] for a in article_list])):
                    self.save_db(total_article_list)
                    return

                total_article_list += article_list
                page += 1

        # endregion
    # endregion