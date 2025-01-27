import React, { useEffect} from 'react';
import Menu from './Menu.jsx';
import { socket } from "../socket";
import icon from './image.png'; // 이미지 파일 가져오기
import { useNavigate, useParams } from "react-router-dom";
import axios from 'axios';
const DownloadPage = () => {
    const navigate = useNavigate();
    const params = useParams();
    useEffect(() => {

        socket.on('connect', async () => {
            console.log('done');
            const filename = `${params.id}.zip`; // 다운로드할 파일 이름
            try {
                const response = await axios.get(`http://localhost:5000/api/download/${filename}`, {
                    responseType: 'blob', // 응답 유형을 blob으로 설정
                });

                // Blob 객체를 URL로 변환
                const url = window.URL.createObjectURL(new Blob([response.data]));

                // a 태그를 생성하여 다운로드 링크 제공
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', filename); // 파일 이름 설정
                document.body.appendChild(link);
                link.click(); // 다운로드 시작
                link.remove(); // 링크 제거
            } catch (error) {
                console.error('Error downloading the file:', error);
            }
            navigate('/list');
        });

        socket.on('disconnect', () => {
            navigate('/list');
        });

        return () => {
            socket.off('connect');
            socket.off('disconnect');
        }
    }, [params.id, navigate]);

    return (
        <div className="main-container">
            <Menu />
            <table>
                <tbody>
                    <tr><td className="a1"></td></tr>
                    <tr><td align="center"><img src={icon} alt="Icon" /></td></tr>
                    <tr><td height="10"></td></tr>
                    <tr><td className="title">다운로드 완료</td></tr>
                    <tr><td height="10"></td></tr>
                    <tr>
                        <td height="50"></td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
};

export default DownloadPage;