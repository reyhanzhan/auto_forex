module.exports = {
  apps: [
    {
      name: "auto-forex",
      cwd: "/home/ubuntu/auto_forex",
      script: "/home/ubuntu/auto_forex/scripts/run_wine_bot.sh",
      autorestart: true,
      max_restarts: 20,
      restart_delay: 10000,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
