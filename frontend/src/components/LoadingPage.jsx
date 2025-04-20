import React, {useEffect, useState} from 'react';
import Menu from './Menu.jsx';
import icon from './image.png'; // 이미지 파일 가져오기
import { useNavigate, useParams } from "react-router-dom";

const LoadingPage = () => {
    const navigate = useNavigate();
    const params = useParams();
    const [loadingText, setLoadingText] = useState("다운로드중");
    const [messages, setMessages] = useState([]);
    const [isPolling, setIsPolling] = useState(true);

    const downloadData = async () => {
        setLoadingText("다운로드 완료");
        setIsPolling(false);

        const filename = `${params.id}.zip`;
        try {
            // 파일 다운로드 (GET 요청)
            const response = await fetch('/api/download/' + filename, {
                method: "GET"
            });

            if (!response.ok) {
                alert("파일 다운로드 실패");
                return;
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
            const deleteResponse = await fetch('/api/delete/' + filename, {
                method: "DELETE"
            });
            if (!deleteResponse.ok) {
                alert("파일 삭제 요청 실패");
            }
        } catch (error) {
            console.error("Error downloading the file:", error);
            alert("파일 다운로드 실패");

        }

        navigate("/list");


    };

    // 일정 간격마다 진행 상황을 요청하는 함수
    function pollProgress() {
        fetch('/api/progress')
            .then(response => response.text()) // Get the response as text
            .then(text => {
                const data = JSON.parse(text); // Parse the text as JSON
                setMessages(data);
            })
            .catch(error => console.error('Error fetching progress:', error));
    }

    useEffect(() => {
        fetch("/api/download_signal/" + params.id)
            .then(response => response.json())
            .then(() => {
                downloadData();
            })
            .catch(error => console.error("Error fetching data:", error));
    }, [params.id]);

    // 컴포넌트가 마운트될 때 폴링 시작
    useEffect(() => {
        if (isPolling) {
            const interval = setInterval(pollProgress, 1000); // Call pollProgress every 5 seconds
            return () => clearInterval(interval); // Cleanup interval on component unmount
        }
    }, [isPolling]);

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
        }, 1000);
        return () => clearInterval(interval);
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
                    <tr><td height="50"></td></tr>
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
