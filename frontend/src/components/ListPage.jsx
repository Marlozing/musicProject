import React, { useEffect, useState, useCallback } from 'react';
import Menu from './Menu.jsx';
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

    // 데이터 새로고침 함수
    const refreshData = useCallback(() => {
        fetch("/api/refresh")
            .then(() => window.location.reload())
            .catch(error => console.error("Error fetching data:", error));
    }, []);


    useEffect(() => {
        fetchData();
    }, [fetchData]);

    return (
        <div className="main-container">
            <Menu/>
            <div className="container">
                <button className={'crawl-button'} onClick={() => {
                    refreshData()
                }}>
                    크롤링하기
                </button>
            </div>
            {Object.entries(items)
                .reverse()
                .map(([key, value]) => (
                    <div className="container" key={key}>
                        <button className="action-button" onClick={() => navigate("/loading/" + key)}>
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