import React from 'react';
import { Link } from 'react-router-dom';
import './MainPage.css'; // CSS 파일 가져오기
import Menu from './Menu.jsx';
import icon from './image.png'; // 이미지 파일 가져오기

const MainPage = () => {
    return (
        <div className="main-container">
            <Menu />

            <table>
                <tbody>
                    <tr><td className="a1"></td></tr>
                    <tr><td align="center"><img src={icon} alt="Example" /></td></tr>
                    <tr><td height="10"></td></tr>
                    <tr><td className="title">시작시간 조절 사이트</td></tr>
                    <tr><td align="center">with Waktaverse Music, Waktaverse Reaction Collection</td></tr>
                    <tr><td height="50"></td></tr>
                    <tr>
                        <td align="center">
                            <Link to="/list" className="a3">시작하기</Link>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
};

export default MainPage;