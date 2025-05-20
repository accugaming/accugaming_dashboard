// server.js

require('dotenv').config();

const express = require('express');
const fetch = require('node-fetch');
const session = require('express-session');
const app = express();

const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;
const REDIRECT_URI = process.env.REDIRECT_URI;
const BOT_ID = process.env.BOT_ID;

app.use(session({ secret: 'secret-key', resave: false, saveUninitialized: true }));

app.get('/login', (req, res) => {
  const discordAuthUrl = `https://discord.com/api/oauth2/authorize?client_id=${CLIENT_ID}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&response_type=code&scope=identify%20guilds`;
  res.redirect(discordAuthUrl);
});

app.get('/callback', async (req, res) => {
  const code = req.query.code;
  if (!code) return res.send('No code provided');

  // Exchange code for access token
  const tokenResponse = await fetch('https://discord.com/api/oauth2/token', {
    method: 'POST',
    body: new URLSearchParams({
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
      grant_type: 'authorization_code',
      code: code,
      redirect_uri: REDIRECT_URI,
      scope: 'identify guilds',
    }),
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  const tokenData = await tokenResponse.json();

  if (tokenData.error) return res.send(`Error getting token: ${tokenData.error_description}`);

  const accessToken = tokenData.access_token;

  // Fetch user info
  const userResponse = await fetch('https://discord.com/api/users/@me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const user = await userResponse.json();

  // Fetch user guilds
  const guildsResponse = await fetch('https://discord.com/api/users/@me/guilds', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const guilds = await guildsResponse.json();

  // Save user and guilds in session
  req.session.user = user;
  req.session.guilds = guilds;

  res.redirect('/dashboard');
});

app.get('/dashboard', async (req, res) => {
  if (!req.session.user || !req.session.guilds) {
    return res.redirect('/login');
  }

  // Check if the user has admin permission on guilds and check if bot is in guilds
  const userGuilds = req.session.guilds.filter(guild => (BigInt(guild.permissions) & BigInt(0x8)) === BigInt(0x8)); // admin perm = 0x8

  // To check if bot is in guild, you would need bot presence data or cache.
  // For demo, let's assume a static list or mark all as without bot.

  // For simplicity, just send the data in an HTML template:
  const BOT_ID = 'YOUR_BOT_ID_HERE'; // replace with your bot user id

  const dashboardHTML = `
  <!DOCTYPE html>
  <html>
  <head>
    <title>Dashboard</title>
    <link rel="stylesheet" href="/style.css" />
  </head>
  <body>
    <header style="display:flex;justify-content:flex-end;align-items:center;padding:20px;background:#eee;">
      <img src="https://cdn.discordapp.com/avatars/${req.session.user.id}/${req.session.user.avatar}.png" alt="Avatar" style="width:50px;height:50px;border-radius:50%;margin-right:10px;" />
      <span style="font-weight:bold;margin-right:20px;">${req.session.user.username}</span>
      <button style="background:#4a90e2;color:white;padding:8px 16px;border:none;border-radius:5px;cursor:pointer;">Premium</button>
    </header>
    <main style="display:flex;flex-wrap:wrap;gap:20px;justify-content:center;padding:20px;">
      ${userGuilds.map(guild => {
        // Replace this with your real check if bot is in guild or not
        const botInGuild = false; // For demo, false for all
        const guildIcon = guild.icon
          ? `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`
          : 'https://via.placeholder.com/180x100?text=No+Icon';
        return `
        <div style="width:180px;position:relative;box-shadow:0 3px 8px rgba(0,0,0,0.1);border-radius:8px;overflow:hidden;cursor:pointer;">
          <img src="${guildIcon}" alt="${guild.name}" style="width:100%;height:100px;object-fit:cover;" />
          <div style="padding:10px;font-weight:bold;text-align:center;">${guild.name}</div>
          <div style="
            position:absolute;
            bottom:10px;
            left:50%;
            transform: translateX(-50%);
            background: rgba(74, 144, 226, 0.85);
            color: white;
            font-weight:700;
            padding:5px 12px;
            border-radius:20px;
            pointer-events:none;
            user-select:none;
          ">
            ${botInGuild ? 'Configure' : 'Add a bot'}
          </div>
        </div>
        `;
      }).join('')}
    </main>
  </body>
  </html>
  `;

  res.send(dashboardHTML);
});

app.listen(3000, () => console.log('Server started on http://localhost:3000'));
