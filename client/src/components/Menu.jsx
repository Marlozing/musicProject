import React from 'react';
import './MainPage.css'; // CSS 파일 가져오기

const Menu = () => {
    return (
        <div className="main-container">
            <table width="100%" border="0">
                <tbody>
                    <tr className="a1" bgcolor="black"><img src="image.png" alt="Example" style={{ float: 'left' }} />
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                    </tr>
                    <tr className="a2">
                        <td className="a2"></td>
                        <td>추가예정</td>
                        <td>추가예정2</td>
                        <td>추가예정3</td>
                        <td>추가예정4</td>
                        <td className="a2"></td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
};

export default Menu;