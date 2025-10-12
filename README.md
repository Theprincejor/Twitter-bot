# Twitter Bot System 🤖

A comprehensive Twitter automation system with Telegram command center that manages multiple worker bots for engagement, following, and content promotion.

## 🌟 Features

- **Telegram Command Center**: Control all bots through a single Telegram interface
- **Multi-Bot Management**: Manage multiple Twitter accounts as worker bots
- **Smart Rate Limiting**: Global rate limiting with automatic cooldowns and captcha handling
- **Cloudflare Bypass**: Automatic Cloudflare protection bypass with cloudscraper
- **Captcha Solving**: Integrated Capsolver for automatic captcha solving
- **Engagement Automation**: Like, comment, retweet, and quote tweets automatically
- **Keyword Targeting**: Search and engage with tweets containing specific keywords
- **User Pool Management**: Build and manage pools of users for mentions
- **Mutual Following**: Automatically sync following relationships between bots
- **Secure Storage**: Encrypted cookie storage for bot authentication
- **Comprehensive Logging**: Both file and Telegram notifications
- **Task Scheduling**: Queue-based task system with priorities and retries

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Telegram Bot   │────│  Task Scheduler  │────│  Worker Manager │
│  Command Center │    │  & Rate Limiter  │    │  (Multiple Bots)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Database      │    │ Twitter Engine   │    │   Logger        │
│ (Encrypted JSON)│    │  (Search & API)  │    │ (File + Telegram)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd Twitter-bot

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp env.example .env
```

### 2. Configuration

Edit `.env` file with your settings:

```env
# Telegram Bot Configuration
TELEGRAM_TOKEN=8350919686:AAG-VPxwYixmm-wpt0Gih37cx2d9mEoyTj4
TELEGRAM_ADMIN_IDS=123456789,987654321

# Security
ENCRYPTION_KEY=your-super-secret-encryption-key-here

# Rate Limiting
LIKE_INTERVAL_MINUTES=2
LIKE_BREAK_MINUTES=10
RATE_LIMIT_PAUSE_MINUTES=20
```

### 3. Get Twitter Cookies

1. Log into your Twitter account in a browser
2. Open Developer Tools (F12)
3. Go to Application/Storage → Cookies
4. Export cookies for `twitter.com` as JSON
5. Save as `cookie1.json`, `cookie2.json`, etc.

### 4. Run the System

```bash
python telegram_bot.py
```

## 📱 Telegram Commands

### Bot Management
- `/addbot <cookie_file>` - Add new worker bot
- `/removebot <bot_id>` - Remove worker bot
- `/listbots` - List all worker bots and status
- `/syncfollows` - Sync mutual following between bots

### Engagement Commands
- `/post <url>` - Like, comment, and retweet a post
- `/like <url>` - Like a specific post
- `/retweet <url>` - Retweet a specific post
- `/comment <url> "<text>"` - Comment on a post
- `/quote <keyword> "<message>"` - Quote tweets with mentions

### Search & Targeting
- `/search <keyword>` - Search for tweets with keyword
- `/pool <keyword>` - Show user pool status
- `/refresh <keyword>` - Refresh user pool

### Monitoring
- `/status` - Show system and bot status
- `/stats` - Show engagement statistics
- `/queue` - Show task queue status
- `/logs` - View recent system logs
- `/backup` - Create database backup

### Cloudflare & Captcha
- `/testlogin` - Test login connectivity and Cloudflare bypass
- `/captchastatus` - Show captcha solver status
- `/cloudflare` - Get Cloudflare cookies for bypass

## 🔧 Configuration Options

### Rate Limiting
```env
LIKE_INTERVAL_MINUTES=2          # Interval between like actions
LIKE_BREAK_MINUTES=10            # Break period after like cycle
COMMENT_MIN_INTERVAL=10          # Minimum comment interval
COMMENT_MAX_INTERVAL=30          # Maximum comment interval
QUOTE_CYCLE_MIN=10               # Minimum quote cycle time
QUOTE_CYCLE_MAX=20               # Maximum quote cycle time
RATE_LIMIT_PAUSE_MINUTES=20      # Pause duration for rate-limited bots

# Captcha Solver Configuration
USE_CAPTCHA_SOLVER=false         # Enable automatic captcha solving
CAPSOLVER_API_KEY=your_key       # Capsolver API key
CAPSOLVER_MAX_ATTEMPTS=3         # Max captcha solve attempts

# Cloudflare Bypass Configuration
USE_CLOUDSCRAPER=false           # Enable Cloudflare bypass
CLOUDSCRAPER_DELAY=2             # Delay between requests
```

### System Settings
```env
MAX_WORKERS=50                   # Maximum number of worker bots
TASK_QUEUE_SIZE=1000            # Maximum tasks in queue
TWITTER_SEARCH_LIMIT=100        # Maximum tweets to search
MAX_MENTIONS_PER_QUOTE=3        # Maximum mentions per quote tweet
```

## 🛡️ Security Features

- **Encrypted Storage**: All cookies and sensitive data encrypted with AES
- **Admin-Only Access**: Commands restricted to configured admin IDs
- **Rate Limit Protection**: Automatic detection and handling of rate limits
- **Captcha Detection**: Automatic pausing when captcha is required
- **Captcha Solving**: Automatic captcha solving with Capsolver integration
- **Cloudflare Bypass**: Bypass Cloudflare protection with cloudscraper
- **Secure Logging**: Sensitive information excluded from logs

## 📊 Monitoring & Logging

### Telegram Notifications
- Bot status updates (active, rate-limited, captcha required)
- Task completion notifications
- Error alerts and system warnings
- Daily statistics summaries

### File Logging
- Detailed logs saved to `logs/bot.log`
- Automatic log rotation (10MB max, 5 backups)
- Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## 🔄 Task Flow

1. **Command Received**: Admin sends command via Telegram
2. **Task Creation**: System creates task with appropriate priority
3. **Rate Limit Check**: Global rate limiter checks if action is allowed
4. **Worker Assignment**: Available workers assigned to task
5. **Execution**: Workers perform actions with staggered timing
6. **Monitoring**: Results logged and admin notified
7. **Cleanup**: Completed tasks cleaned up after 1 hour

## 🚨 Error Handling

### Rate Limits
- Automatic detection of 429/403 responses
- Bots paused for configured duration
- Telegram notifications sent to admin
- Automatic resumption when cooldown expires

### Captcha Challenges
- Detection of captcha requirements
- Immediate bot pausing
- Critical alerts to admin
- Manual intervention required

### Network Issues
- Automatic retry with exponential backoff
- Graceful degradation on failures
- Comprehensive error logging

## 📁 Project Structure

```
Twitter-bot/
├── config.py              # Configuration management
├── database.py            # Encrypted JSON database
├── logger.py              # Logging system
├── worker_manager.py      # Twitter worker bot management
├── scheduler.py           # Task scheduling and rate limiting
├── twitter_engine.py      # Twitter search and engagement
├── telegram_bot.py        # Main Telegram command center
├── requirements.txt       # Python dependencies
├── env.example           # Environment variables template
├── README.md             # This file
├── data/                 # Data storage directory
│   ├── database.json     # Encrypted main database
│   └── cookies/          # Cookie files directory
└── logs/                 # Log files directory
    └── bot.log           # Main log file
```

## 🔧 Advanced Usage

### Custom Engagement Strategies

```python
# Example: Custom quote campaign
await scheduler.add_task(
    TaskType.QUOTE,
    {
        'keyword': 'cryptocurrency',
        'quote_text': 'Great insights on crypto! 🚀',
        'mention_count': 5
    },
    priority=2,
    delay_minutes=5
)
```

### Building User Pools

```python
# Search and build user pool
tweets = await search_engine.search_tweets_by_keyword('bitcoin')
users = await search_engine.extract_users_from_tweets(tweets)
await search_engine.build_user_pool_for_keyword('bitcoin', users)
```

## 🐛 Troubleshooting

### Common Issues

1. **Bot Authentication Failed**
   - Check cookie file format
   - Ensure cookies are fresh (not expired)
   - Verify auth_token and ct0 are present

2. **Rate Limit Errors**
   - Increase rate limit intervals in config
   - Reduce number of active workers
   - Check Twitter's current rate limits

3. **Telegram Bot Not Responding**
   - Verify TELEGRAM_TOKEN is correct
   - Check TELEGRAM_ADMIN_IDS format
   - Ensure bot is running and accessible

4. **Database Errors**
   - Check ENCRYPTION_KEY is set correctly
   - Verify data directory permissions
   - Try creating fresh database backup

### Debug Mode

Enable debug logging:
```env
LOG_LEVEL=DEBUG
```

View detailed logs:
```
/logs 100
```

## 📈 Performance Optimization

- **Async Operations**: All operations are asynchronous for better performance
- **Connection Pooling**: Reuse connections where possible
- **Caching**: Search results cached for 1 hour
- **Batch Processing**: Multiple actions batched together
- **Smart Scheduling**: Tasks scheduled to avoid conflicts

## 🔮 Future Enhancements

- [ ] Twitter API v2 integration
- [ ] Advanced analytics dashboard
- [ ] Machine learning for engagement optimization
- [ ] Multi-language support
- [ ] Web interface for management
- [ ] Advanced targeting options
- [ ] A/B testing capabilities

## ⚠️ Legal Disclaimer

This software is for educational purposes only. Users are responsible for complying with Twitter's Terms of Service and applicable laws. The authors are not responsible for any misuse of this software.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the logs for error details

---

**Happy Botting! 🤖✨**
#   W e b h o o k   t e s t   a f t e r   f i x i n g   s e c r e t s   1 0 / 1 2 / 2 0 2 5   0 1 : 2 2 : 0 9  
 #   W e b h o o k   t e s t   f r o m   l o c a l   m a c h i n e   1 0 / 1 2 / 2 0 2 5   0 1 : 2 3 : 5 4  
 #   F i n a l   w e b h o o k   t e s t   1 0 / 1 2 / 2 0 2 5   0 1 : 2 4 : 5 6  
 