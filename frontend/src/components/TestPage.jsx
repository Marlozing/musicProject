import React, { useEffect } from 'react';
import Menu from './Menu.jsx';
import { socket } from "../socket";

const TestPage = () => {
    useEffect(() => {
        socket.on('done', (data) => {
            window.location.href = "/list";
        });

        return () => {
            socket.off('done');
        }
    }, []);

    const test = () => {
        console.log(socket.connected);
        socket.emit('signal', { "link": "https://www.youtube.com/watch?v=6n3pFFPSlW4", "reactions": "100" });
    }

    return (
        <div className="main-container">
            <Menu />
            <table>
                <tbody>
                    <tr><td className="a1"></td></tr>
                    <tr><td align="center"><img src="image.png" alt="Example" /></td></tr>
                    <tr><td height="10"></td></tr>
                    <tr><td className="title">다운로드중</td></tr>
                    <tr><td><button onClick={() => test()}>test</button></td></tr>
                    <tr><td align="center">with Waktaverse Music, Waktaverse Reaction Collection</td></tr>
                    <tr><td height="50"></td></tr>
                </tbody>
            </table>
        </div>
    );
}

export default TestPage;