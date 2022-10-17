# Secret Santa Bot

I wrote this bot to help create Secret Santas that I could organise remotely without having to know who will get me as
their Secret Santa.

## Creating a Secret Santa

1. Setup you environment (`pipenv install` or whatever virtual env you use)
2. Copy settings.default.yml to settings.yml
3. Update the default settings for your Secret Santa.
4. For your e-mail password, you can either tell the solver to read it from an env var with a dollar sign prefix,
   e.g. `$ENV_VAR_NAME`, or put the password directly into settings.yml.
5. Run the solver. By default the solver will run in dry-run mode, which will show you example e-mail outputs.
   If you want to actually send e-mails, use the `--no-dry-run` flag. If you want to test e-mail sending capabilities,
   use `--test-email`. Be careful not to actually send e-mails before you have everyone's details!

Every time you run the program it will generate new pairings.

## Customising e-mails

You can customise the format of e-mails by editing the `email_template.j2` Jinja template.

## Notes

* Secret Santa e-mails will likely appear in your Sent folder. Make sure you either can resist the urge to open them,
or delete them immediately.