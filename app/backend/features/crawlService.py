import sqlite3
import os
from uuid import uuid4
from httpx import AsyncClient, AsyncHTTPTransport
from dotenv import load_dotenv

class CrawlService:
    def __init__(self):
        # httpx AsyncHTTPTransport 초기화
        self.transport = AsyncHTTPTransport(retries=1)

        # 유저의 게시물 링크를 저장할 DB
        self.db_conn = sqlite3.connect("./database/posted_link.db")

        load_dotenv("crawl.env")
    async def check_new_posts(self, max_page: int):
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

        async with AsyncClient(transport=self.transport) as client:
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

            # 게시물 리스트 중에서 반응정리 팀의 게시물을 찾음
            article_list = []
            for article in response.json()["message"]["result"]["articleList"]:
                if article["memberKey"] == os.getenv("NAVER_CAFE_REACTION_MEMBERKEY"):
                    article_list.append(article)
            # endregion

            # region DB에 저장
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
                else:
                    # 링크가 존재할 경우, 제목이 변경되었는지 확인
                    if existing_title[0] != str(article["subject"]):
                        db_cur.execute(
                            "UPDATE posted_link SET title = ? WHERE link = ?",
                            (str(article["subject"]), article_id),
                        )
            # endregion

            self.db_conn.commit()
