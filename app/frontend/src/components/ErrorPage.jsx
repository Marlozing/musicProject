import React, { useEffect } from 'react';
import Menu from './Menu.jsx';
import { socket } from "../socket";
import icon from './image.png'; // 이미지 파일 가져오기
import { useNavigate } from "react-router-dom";
const ErrorPage = () => {
    const navigate = useNavigate();
    useEffect(() => {

        socket.on('connect', () => {
            navigate('/');
        });

        return () => {
            socket.off('connect');
        }
    }, [navigate]);

    return (
        <div className="main-container">
            <Menu />
            <table>
                <tbody>
                    <tr><td className="a1"></td></tr>
                    <tr><td align="center"><img src={icon} alt="Icon" /></td></tr>
                    <tr><td height="10"></td></tr>
                    <tr><td className="title">현재 서버가 열려있지 않습니다.</td></tr>
                    <tr><td className="title">서버가 열릴 시 이동됩니다.</td></tr>
                    <tr><td height="10"></td></tr>
                    <tr><td height="50"></td></tr>
                </tbody>
            </table>
        </div>
    );
};

export default ErrorPage;