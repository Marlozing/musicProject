import React, { useEffect, useState } from 'react';
import Menu from './Menu.jsx';
import { socket, API_URL } from "../socket";
import icon from './image.png'; // 이미지 파일 가져오기
import { useNavigate, useParams } from "react-router-dom";

const LoadingPage = () => {
    const navigate = useNavigate();
    const params = useParams();
    const [loadingText, setLoadingText] = useState("다운로드중");
    const [messages, setMessages] = useState([]);

    useEffect(() => {
        // 실시간 진행 상황 업데이트
        socket.on('progress_update', (data) => {
            setMessages(prevMessages => [...prevMessages, data.message]);
        });

        // 다운로드 완료 이벤트 처리
        socket.on("done", async () => {
            setLoadingText("다운로드 완료");
            setMessages([]);

            const filename = `${params.id}.zip`;
            console.log(filename);

            try {
                // 파일 다운로드 (GET 요청)
                const response = await fetch(`${API_URL}/download/${filename}`, {
                    method: "GET"
                });
                if (!response.ok) {
                    throw new Error("네트워크 응답 오류");
                }
                const blob = await response.blob();

                // Blob URL 생성 및 임시 a 태그로 다운로드 트리거
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.setAttribute("download", filename);
                document.body.appendChild(link);
                link.click();
                window.URL.revokeObjectURL(url);
                link.remove();

                // 다운로드 후 파일 삭제 (DELETE 요청)
                const deleteResponse = await fetch(`${API_URL}/delete/${filename}`, {
                    method: "DELETE"
                });
                if (!deleteResponse.ok) {
                    throw new Error("파일 삭제 요청 실패");
                }
            } catch (error) {
                console.error("Error downloading the file:", error);
            }

            navigate("/list");
        });

        // Socket 연결 종료 시 목록 페이지로 이동
        socket.on('disconnect', () => {
            navigate('/list');
        });

        return () => {
            socket.off('progress_update');
            socket.off('done');
            socket.off('disconnect');
        };
    }, [params.id, navigate]);

    useEffect(() => {
        // 로딩 텍스트 애니메이션 (500ms마다 점 추가)
        const interval = setInterval(() => {
            setLoadingText(prev => {
                if (prev === "다운로드 완료") {
                    return "다운로드 완료";
                } else if (prev === "다운로드중...") {
                    return "다운로드중";
                } else {
                    return prev + ".";
                }
            });
        }, 500);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="main-container">
            <Menu />
            <table>
                <tbody>
                    <tr>
                        <td className="a1"></td>
                    </tr>
                    <tr>
                        <td align="center">
                            <img src={icon} alt="Icon" />
                        </td>
                    </tr>
                    <tr>
                        <td height="10"></td>
                    </tr>
                    <tr>
                        <td className="title">{loadingText}</td>
                    </tr>
                    <tr>
                        <td height="10"></td>
                    </tr>
                    <tr>
                        <td height="50"></td>
                    </tr>
                </tbody>
            </table>
            <div>
                <h2>진행 상황</h2>
                <ul style={{ listStyle: "none", padding: 0 }}>
                    {messages.map((message, index) => (
                        <li key={index}>{message}</li>
                    ))}
                </ul>
            </div>
        </div>
    );
};

export default LoadingPage;
