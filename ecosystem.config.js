module.exports = {
  apps: [
    {
      name: "auto-forex",
      cwd: "/home/ubuntu/auto_forex",
      script: "/home/ubuntu/auto_forex/.venv/bin/python",
      args: "-m forex_bot.main",
      autorestart: true,
      max_restarts: 20,
      restart_delay: 10000,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
