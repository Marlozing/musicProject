import React, { useEffect, useState } from 'react';
import Menu from './Menu.jsx';
import { io } from 'socket.io-client';

const socket = io('http://localhost:5000');

const ListPage = () => {
    const [items, setItems] = useState({});

    useEffect(() => {
        fetch('/api/data')  // Flask API call
            .then(response => response.json())
            .then(data => setItems(data))
            .catch(error => console.error('Error fetching data:', error));
    }, []);

    useEffect(() => {
        // Listen for refresh signal from server
        socket.on('refresh', () => {
            console.log("Refresh signal received from server");
            window.location.reload();  // Refresh the page
        });

        return () => {
            socket.off('refresh'); // Clean up event listener on component unmount
        };
    }, []);

    const handleButtonClick = (key, value) => {
        window.location.href = "/loading";
        // Send POST request to API
        fetch('/api/signal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ "link": key, "reactions": value }), // Data to send: key, title
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
                        // Send POST request to API
                        fetch('/api/refresh', {
                            method: 'POST',
                        })
                        .then(response => {
                            if (response.ok) {
                                return response.json();
                            }
                            throw new Error('Network response was not ok.');
                        })
                        .then(data => {
                            console.log(data.message); // Log response message
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
                        onClick={() => handleButtonClick(key, value[1])} // Send key on button click
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