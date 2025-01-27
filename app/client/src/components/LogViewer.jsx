// LogViewer.jsx
import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';

const LogViewer = () => {
    const [logs, setLogs] = useState([]);

    useEffect(() => {
        const socket = io('http://localhost:5000');

        socket.on('log', (data) => {
            setLogs((prevLogs) => [...prevLogs, data.message]);
        });

        return () => {
            socket.disconnect();
        };
    }, []);

    return (
        <div>
            <h2>Logs</h2>
            <ul>
                {logs.map((log, index) => (
                    <li key={index}>{log}</li>
                ))}
            </ul>
        </div>
    );
};

export default LogViewer;