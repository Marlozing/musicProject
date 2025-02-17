import React, { useEffect, useState, useCallback } from 'react';
import Menu from './Menu.jsx';
import { socket } from "../socket";
import { useNavigate } from "react-router-dom";
import Twemoji from 'react-twemoji';
import "./ListPage.css";


const ListPage = () => {
    const [items, setItems] = useState({});
    const navigate = useNavigate();

    // 데이터 가져오는 함수
    const fetchData = useCallback(() => {
        fetch("/api/data")
            .then(response => response.json())
            .then(data => setItems(data))
            .catch(error => console.error("Error fetching data:", error));
    }, []);

    // 페이지 마운트 시 데이터 로드 및 소켓 이벤트 리스너 설정
    useEffect(() => {
        fetchData();

        const handleRefresh = () => window.location.reload();
        const handleDisconnect = () => navigate("/error");

        socket.on("refresh", handleRefresh);
        socket.on("disconnect", handleDisconnect);

        return () => {
            socket.off("refresh", handleRefresh);
            socket.off("disconnect", handleDisconnect);
        };
    }, [fetchData, navigate]);

    // 버튼 클릭 핸들러
    const handleButtonClick = (key) => {
        socket.emit("download_signal", key);
        navigate(`/loading/${key}`);
    };

    return (
        <div className="main-container">
            <Menu/>
            <div className="container">
                <button className={'crawl-button'} onClick={() => {
                    socket.emit('refresh');
                }}>
                    크롤링하기
                </button>
            </div>
            {Object.entries(items)
                .reverse()
                .map(([key, value]) => (
                    <div className="container" key={key}>
                        <button className="action-button" onClick={() => handleButtonClick(key)}>
                            {value[0]}
                        </button>
                        <div className="emoji-box">
                            <Twemoji options={{className: 'custom-twemoji'}}>
                                {value[1]}
                            </Twemoji>
                        </div>
                    </div>
                ))}
        </div>
    );
};

export default ListPage;