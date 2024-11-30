import React, { useState, useEffect } from 'react';
import Menu from './Menu.jsx';
import {io} from "socket.io-client";

const socket = io('http://localhost:5000');

const LoadingPage = () => {
    const [loadingText, setLoadingText] = useState("다운로드중");

    useEffect(() => {
        const interval = setInterval(() => {
        setLoadingText(prev => {
        if (prev === "다운로드중...") {
            return "다운로드중";
        } else {
            return prev + ".";
        }
            });
        }, 500); // 500ms마다 업데이트

        return () => clearInterval(interval); // 컴포넌트 언마운트 시 interval 정리
    }, []);

    useEffect(() => {
        // 서버에서 새로 고침 신호 수신
        socket.on('done', () => {
            console.log("Done signal received from server");
            window.location.href = "/list";  // 페이지 새로 고침
        });

        return () => {
            socket.off('done'); // 컴포넌트 언마운트 시 이벤트 리스너 정리
        };
    }, []);

    return (
        <div className="main-container">
            <Menu />
            <table>
                <tbody>
                    <tr><td className="a1"></td></tr>
                    <tr><td align="center"><img src="image.png" alt="Example" /></td></tr>
                    <tr><td height="10"></td></tr>
                    <tr><td className="title">{loadingText}</td></tr>
                    <tr><td align="center">with Waktaverse Music, Waktaverse Reaction Collection</td></tr>
                    <tr><td height="50"></td></tr>
                </tbody>
            </table>
        </div>
    );
};

export default LoadingPage;