This project is a management tool for a group of volunteers "Protezione Civile".

Every volunteer (Volontario) is added in the database through the Volontario model.
They are tracked by their Italian "Codice Fiscale"

This tool can be used by the admin personnnel through the Django Admin pages, but its crown jewel is the Telegram Bot.

Every Volontario is linked to the system through his or her Telegram account. The Bot is the main way for laypeople to interact with this system.

The tool has two main functions for now:
- Calendar system (Servizio, ScheduledTask) to alert volunteers about the upcoming things to do and have them sign up through a Telegram poll
- Time-keeping, volunteers can clock in and out.