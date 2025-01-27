import React, { useEffect, useState } from 'react';
import Menu from './Menu.jsx';
import { socket } from "../socket";
import { useNavigate } from "react-router-dom";

const ListPage = () => {
    const [items, setItems] = useState({});
    const navigate = useNavigate();
    useEffect(() => {

        fetch('/api/data')  // Flask API call
            .then(response => response.json())
            .then(data => setItems(data))
            .catch(error => console.error('Error fetching data:', error));

        // Listen for refresh signal from server
        socket.on('refresh', () => {
            window.location.reload();  // Refresh the page
        });

        socket.on('disconnect', () => {
            navigate('/error'); // Navigate to error page on disconnect
        });

        return () => {
            socket.off('refresh'); // Clean up event listener on component unmount
            socket.off('disconnect');
        };

    }, [navigate]);

    const handleButtonClick = (key) => {
        socket.emit('download_signal', key); // Send key to server
        navigate(`/loading/` + key); // Navigate to loading page
    };

    return (
        <div className="main-container">
            <Menu />
            <div style={{ display: 'flex', justifyContent: 'center' }}>
                <button
                    style={{ width: '100%', height: '4vh', fontSize: '1.6em' }}
                    onClick={() => {
                        // Send POST request to API
                        socket.emit('refresh');
                    }}
                >
                    크롤링하기
                </button>
            </div>
            {Object.entries(items).map(([key, value]) => (
                <div style={{ display: 'flex', justifyContent: 'center' }} key={key}>
                    <button
                        style={{ width: '150%', fontSize: '1.6em' }}
                        onClick={() => handleButtonClick(key)} // Send key on button click
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