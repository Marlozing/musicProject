import { io } from 'socket.io-client';

// Socket 연결용 URL (WebSocket)
export const SOCKET_URL = process.env.NODE_ENV === 'production'
    ? `ws://${window.location.hostname}:5000`
    : `ws://${window.location.hostname}:5000`;

export const API_URL = process.env.NODE_ENV === 'production'
    ? `http://${window.location.hostname}:5000/api`
    : `http://${window.location.hostname}:5000/api`;

// Socket.IO 인스턴스 생성 (WebSocket 전용)
export const socket = io(SOCKET_URL, {
    transports: ['websocket'], // WebSocket 우선 사용
    withCredentials: true,     // CORS 문제 방지
});
