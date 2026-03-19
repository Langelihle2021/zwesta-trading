# Clear All Bots - Usage Guide

## Quick Start

To clear all bots and start fresh:

```bash
# Interactive mode (recommended - asks for confirmation)
python clear_all_bots.py

# Automatic mode (no confirmation)
python clear_all_bots.py --confirm

# Dry run (shows what would be deleted without deleting)
python clear_all_bots.py --dry-run

# Clear only specific user's bots
python clear_all_bots.py --user your_user_id --confirm
```

## What Gets Deleted ✅

- ✅ All bot configurations
- ✅ All trade histories
- ✅ All daily profit records
- ✅ All bot-credential links
- ✅ All running bot threads

## What Gets Kept ✅

- ✅ Broker credentials (Exness, XM Global, Binance)
- ✅ Account balance (real broker data)
- ✅ User account data
- ✅ Commission records
- ✅ All broker settings

## Examples

### 1. **Clear All Bots (Interactive)**
```bash
python clear_all_bots.py
```

Output:
```
============================================================
ZWESTA BOT CLEAR UTILITY - Fresh Start
============================================================

📋 Found 54 bot(s) to delete:

  User: user_12345 (54 bots)
    • bot_1234567_abc
      Name: BTC Trader, Strategy: Trend Following, 🟢 ENABLED
    • bot_1234568_def
      Name: EUR Scalper, Strategy: Mean Reversion, 🔴 DISABLED
    ...

⚠️  WARNING: This will DELETE 54 bot(s) PERMANENTLY!
   • All bot configurations will be removed
   • All trade histories will be deleted
   • All daily profits will be cleared
   • Running bots will be stopped

✅ Keep: Broker credentials, account balance, user data

Type 'YES' to proceed: YES

📦 Creating backup...
✅ Database backed up to: backups/trading_bots_backup_20260319_155432.db

🗑️  Deleting bots from database...
✅ Deleted successfully!

✅ COMPLETE: 54 bot(s) deleted successfully
📂 Backup saved in: backups/

You can now start fresh with new bots!
```

### 2. **Dry Run (Preview Only)**
```bash
python clear_all_bots.py --dry-run
```

Output:
```
🔍 DRY RUN: Would delete 54 bot(s)
Use --confirm to actually delete
```

### 3. **Auto-Delete Without Confirmation**
```bash
python clear_all_bots.py --confirm
```

⚠️ **WARNING**: This will delete immediately without asking!

### 4. **Clear Bots for Specific User**
```bash
python clear_all_bots.py --user user_12345 --confirm
```

## Recovery

If you accidentally delete bots, you can restore from backup:

```bash
# 1. Find your backup in the backups/ folder
ls backups/

# 2. Restore it (ask for help if needed)
# Your backup file name will be: trading_bots_backup_YYYYMMDD_HHMMSS.db
```

## Command Options

| Option | Effect |
|--------|--------|
| `--dry-run` | Show what would be deleted (no actual deletion) |
| `--confirm` | Skip confirmation prompt (delete immediately) |
| `--user USER_ID` | Delete only bots for specific user |

## Combining Options

```bash
# Dry run for specific user
python clear_all_bots.py --user user_12345 --dry-run

# Clear specific user's bots without confirmation
python clear_all_bots.py --user user_12345 --confirm
```

## After Deletion

Once you've cleared all bots:

1. **Verify clearing worked:**
   - Open dashboard → should show 0 bots
   - Check `/api/user/dashboard` → `total_bots: 0`

2. **Start fresh:**
   - Go to "Create Bot" 
   - Select your broker (Exness, XM Global, or Binance)
   - Create new bot with your desired settings

3. **Your broker balance is still there:**
   - Exness: $196,229.68 (unchanged)
   - All other integrations: still connected

## Safety Features

✅ **Automatic Backup**: Creates database backup before deletion  
✅ **Confirmation Prompt**: Asks "Type 'YES'" to prevent accidents  
✅ **Dry Run Mode**: Preview deletions without making them  
✅ **Transaction Safety**: Uses database transactions  
✅ **Error Handling**: Graceful failures with clear messages  

## Troubleshooting

### "Database not found"
```
✅ Make sure trading_bots.db exists in the same folder as this script
```

### "Backup failed"
```
✅ Make sure you have write permissions in the script directory
✅ Check that backups/ folder can be created
```

### "No bots found"
```
✅ You already have no bots - system is clean!
```

## Questions?

This script safely clears your bots while:
- ✅ Keeping broker credentials intact
- ✅ Preserving account balance
- ✅ Creating automatic backup
- ✅ Asking for confirmation

**The system is now ready for a fresh start!** 🚀
