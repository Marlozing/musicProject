import React, { useEffect, useState } from 'react';
import Menu from './Menu.jsx';
import { socket, BASE_URL } from "../socket";
import icon from './image.png'; // 이미지 파일 가져오기
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";

const LoadingPage = () => {
    const navigate = useNavigate();
    const params = useParams();
    const [loadingText, setLoadingText] = useState("다운로드중");
    const [messages, setMessages] = useState([]);

    useEffect(() => {
        socket.on('progress_update', (data) => {
            setMessages(prevMessages => [...prevMessages, data.message]);
        });

        socket.on("done", async () => {
            setLoadingText("다운로드 완료");
            setMessages([]);

            const filename = `${params.id}.zip`;
            try {
                const response = await axios.get(`${BASE_URL}/api/download/${filename}`, {
                    responseType: "blob", // 응답을 blob으로 받음
                });

                // Blob URL 생성
                const blob = new Blob([response.data]);
                const url = window.URL.createObjectURL(blob);

                // a 태그를 이용해 다운로드 처리
                const link = document.createElement("a");
                link.href = url;
                link.setAttribute("download", filename);
                document.body.appendChild(link);
                link.click();

                // 사용한 Blob URL 해제 (메모리 절약)
                window.URL.revokeObjectURL(url);
                link.remove();

                // 다운로드 후 파일 삭제 요청
                await axios.delete(`${BASE_URL}/api/delete/${filename}`);
            } catch (error) {
                console.error("Error downloading the file:", error);
            }

            navigate("/list");
        });


        socket.on('disconnect', () => {
            navigate('/list');
        });

        return () => {
            socket.off('progress_update');
            socket.off('done');
            socket.off('disconnect');
        }
    }, [params.id, navigate]);

    useEffect(() => {
        const interval = setInterval(() => {
            setLoadingText(prev => {
                if (prev === "다운로드 완료") {
                    return "다운로드 완료";
                } else if (prev === "다운로드중...") {
                    return "다운로드중";
                }else{
                    return prev + ".";
                }
            });
        }, 500); // 500ms마다 업데이트

        return () => clearInterval(interval); // 컴포넌트 언마운트 시 interval 정리
    }, []);

    return (
        <div className="main-container">
            <Menu />
            <table>
                <tbody>
                    <tr><td className="a1"></td></tr>
                    <tr><td align="center"><img src={icon} alt="Icon" /></td></tr>
                    <tr><td height="10"></td></tr>
                    <tr><td className="title">{loadingText}</td></tr>
                    <tr><td height="10"></td></tr>
                    <tr>
                        <td height="50"></td>
                    </tr>
                </tbody>
            </table>
            <div>
                <h2>진행 상황</h2>
                <ul style={{listStyle: "none", padding: 0}}>
                    {messages.map((message, index) => (
                        <li key={index}>{message}</li>
                    ))}
                </ul>
            </div>
        </div>
    );
};

export default LoadingPage;