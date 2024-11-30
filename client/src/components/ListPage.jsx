import React, { useEffect, useState } from 'react';
import Menu from './Menu.jsx';
import { io } from 'socket.io-client';

const socket = io('http://localhost:5000');

const ListPage = () => {
    const [items, setItems] = useState({});

    useEffect(() => {
        fetch('/api/data')  // Flask API 호출
            .then(response => response.json())
            .then(data => setItems(data))
            .catch(error => console.error('Error fetching data:', error));
    }, []);

    useEffect(() => {
        // 서버에서 새로 고침 신호 수신
        socket.on('refresh', () => {
            console.log("Refresh signal received from server");
            window.location.reload();  // 페이지 새로 고침
        });

        return () => {
            socket.off('refresh'); // 컴포넌트 언마운트 시 이벤트 리스너 정리
        };
    }, []);

    const handleButtonClick = (key) => {
        window.location.href = "/loading";
        // API로 POST 요청 보내기
        fetch('/api/signal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ link: key }), // 전송할 데이터: key
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok.');
        })
        .catch(error => {
            console.error('Error:', error);
        });
    };

    return (
        <div className="main-container">
            <Menu />
            <div style={{ display: 'flex', justifyContent: 'center' }}>
                <button
                    style={{ width: '100%', height: '4vh', fontSize: '1.6em' }}
                    onClick={() => {
                        // API로 POST 요청 보내기
                        fetch('/api/trigger_refresh', {
                            method: 'POST',
                        })
                        .then(response => {
                            if (response.ok) {
                                return response.json();
                            }
                            throw new Error('Network response was not ok.');
                        })
                        .then(data => {
                            console.log(data.message); // 응답 메시지 출력
                        })
                        .catch(error => {
                            console.error('Error:', error);
                        });
                    }}
                >
                    크롤링하기
                </button>
            </div>
            {Object.entries(items).map(([key, value]) => (
                <div style={{ display: 'flex', justifyContent: 'center' }} key={key}>
                    <button
                        style={{ width: '150%', fontSize: '1.6em' }}
                        onClick={() => handleButtonClick(key)} // 버튼 클릭 시 key 전송
                    >
                        {value[0]}
                    </button>
                    <div style={{ width: '50%', fontSize: '1.6em', textAlign: 'left', border: '1px solid black' }}>
                        {value[1]}
                    </div>
                </div>
            )).reverse()}
        </div>
    );
};

export default ListPage;
