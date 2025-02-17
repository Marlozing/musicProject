import React from 'react';
import { BrowserRouter, Route, Routes} from 'react-router-dom';
import MainPage from './components/MainPage'; // MainPage 가져오기
import ListPage from './components/ListPage'; // TestPage 컴포넌트 가져오기
import LoadingPage from './components/LoadingPage';
import ErrorPage from './components/ErrorPage';
import TestPage from "./components/TestPage";
function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" exact element={<MainPage />} />
                <Route path="/list" element={<ListPage />} />
                <Route path="/loading/:id" element={<LoadingPage />} />
                <Route path="/test" element={<TestPage />} />
                <Route path="/error" element={<ErrorPage />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;