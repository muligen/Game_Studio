/**
 * Application Entry Point
 *
 * Initializes and renders the React application
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/SnakeGame.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
