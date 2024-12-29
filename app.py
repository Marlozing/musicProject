import sys
import os

from dotenv import load_dotenv


if __name__ == "__main__":

    load_dotenv(".env")
    NAVER_ID = os.getenv("NAVER_ID")
    NAVER_PW = os.getenv("NAVER_PW")
    if len(sys.argv) != 3:
        # 환경 변수 가져오기
        if not NAVER_ID or not NAVER_PW:
            print("Usage: python routes.py [NAVER_ID] [NAVER_PW]")
            sys.exit(1)
        else:
            print("Using environment variables")
    else:
        NAVER_ID = sys.argv[1]
        NAVER_PW = sys.argv[2]

        with open(".env", "w") as f:
            f.write(f"NAVER_ID = {NAVER_ID}\n")
            f.write(f"NAVER_PW = {NAVER_PW}\n")

        print("Environment variables saved")

    from app import create_app, socketio

    app = create_app(debug=True)
    socketio.run(app)
