import React, { useEffect, useState } from 'react';
import Menu from './Menu.jsx';
import { socket } from "../socket";
import icon from './image.png'; // 이미지 파일 가져오기
import { useNavigate, useParams } from "react-router-dom";
import axios from 'axios';
const LoadingPage = () => {
    const navigate = useNavigate();
    const params = useParams();
    const [loadingText, setLoadingText] = useState("다운로드중");

    useEffect(() => {
        socket.on('test', (data) => {
            console.log(data.message);
        });

        socket.on('done', () => {
            navigate(`/download/${params.id}`);
        });

        socket.on('disconnect', () => {
            navigate('/list');
        });

        return () => {
            socket.off('test');
            socket.off('done');
            socket.off('disconnect');
        }
    }, [params.id, navigate]);

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
        </div>
    );
};

export default LoadingPage;