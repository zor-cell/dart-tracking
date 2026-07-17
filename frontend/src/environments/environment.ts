const wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';

export const environment = {
  production: true,
  httpApiUrl: '/api',
  wsApiUrl: `${wsProtocol}://${location.host}/api/ws`
};
