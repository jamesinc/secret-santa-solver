
import os
import time
import jinja2
import random
import smtplib
import argparse
from datetime import date
from copy import deepcopy

import yaml
from schema import Schema, SchemaError, Or, And
from email_validator import validate_email, EmailNotValidError, caching_resolver


class DeadEndException(Exception):
    """
    Raised if the solver fails to successfully pair everyone. The random nature of the solver means
    this happens occasionally.
    """


def email_is_valid(email, resolver=None):
    """
    Bool wrapper for validate_email

    Args:
        email (str): The e-mail address to validate
        resolver (email_validator.caching_Resolver, optional): e-mail validator resolver object. Defaults to None.

    Returns:
        bool: True if e-mail is valid
    """
    try:
        validate_email(email, dns_resolver=resolver)
    except EmailNotValidError:
        return False

    return True


def validate_settings(settings):
    """
    Validate Secret Santa settings dict

    Args:
        settings (str): the loaded settings dict

    Returns:
        bool: True if settings are valid
    """

    resolver = caching_resolver(timeout=10)
    settings_schema = Schema({
        "config": {
            "email_subject": str,
            "smtp": {
                "host": str,
                "port": int,
                "user": And(str, lambda x: email_is_valid(x, resolver)),
                "password": str
            },
            "testing": {
                "name": str,
                "email": And(str, lambda x: email_is_valid(x, resolver))
            }
        },
        "rules": {
            "limit_dollars": And(Or(int, float), lambda x: x > 0),
            "opening_day": date
        },
        "participants": [{
            "name": str,
            "email": And(str, lambda x: email_is_valid(x, resolver))
        }]
    })


    try:
        settings_schema.validate(settings)
    except SchemaError as schema_error:
        print(schema_error)
        return False
    
    print("Settings validated successfully!")
    print("")

    return True


def load_settings():
    """
    Loads config from settings.yml

    Returns:
        tuple(dict, dict, dict): config, rules, and participants list
    """

    with open("settings.yml", "r") as fh:
        settings = yaml.safe_load(fh)
        valid = validate_settings(settings)

    if not valid:
        print("")
        print("*** Quitting due to errors ***")
        exit(1)

    return settings["config"], settings["rules"], settings["participants"]


def solve(participants):
    """
    Generate the secret santa giver/receiver pairs

    Args:
        participants (list): A list of participants

    Raises:
        DeadEndException: Raised if the solver goes down a path that cannot lead to a solution

    Returns:
        list: A list of [giver, receiver] pairs
    """

    givers = deepcopy(participants)
    receivers = deepcopy(participants)
    pairs = []

    # Randomise the receiver list
    random.shuffle(receivers)

    for giver in givers:
        # There's a chance that a giver will be randomly assigned to themselves, so we will keep randomly
        # picking receivers in a loop until we get one that isn't the giver
        while True:
            receiver = random.choice(receivers)

            if receiver == giver:
                # Check that this isn't the last people in each list
                # If it is, this permutation of givers and receivers **will not work**
                # and the script must be re-run to generate a new random assortment
                if len(receivers) == 1:
                    raise DeadEndException("Hit a dead-end while solving")
            else:
                pairs.append([giver, receiver])
                # We have successfully paired a giver and receiver.
                # We can now remove the receiver from the receiver list
                # so that they don't get paired with multiple people.
                receivers.remove(receiver)
                break
        
    # This is a paranoia test to ensure everyone gives once and receives once
    for person in participants:
        giveCount = 0
        receiveCount = 0

        for pair in pairs:
            if pair[0]["name"] == person["name"]:
                giveCount += 1
            
            if pair[1]["name"] == person["name"]:
                receiveCount += 1

        assert giveCount == 1, 'Each person should be a giver exactly once'
        assert receiveCount == 1, 'Each person should be a receiver exactly once'

    return pairs


def send_emails(config, rules, pairs, dry_run):
    """
    Sends e-mails to participants

    Args:
        pairs (list): List of pairings
    """

    with open("email_template.j2", "r") as fh:
        email_tpl = jinja2.Template(fh.read())

    try:
        server = smtplib.SMTP_SSL(config["smtp"]["host"], config["smtp"]["port"])
        email_from = config["smtp"]["user"]

        if not dry_run:
            server.ehlo()
            server.login(
                user=config["smtp"]["user"],
                password=config["smtp"]["password"]
            )

        for giver, receiver in pairs:
            email_to = giver['email']
            email_body = email_tpl.render(
                sender=config["smtp"]["user"],
                giver=giver,
                receiver=receiver,
                subject=config["email_subject"],
                **rules
            )

            if not dry_run:
                print(f"Sending e-mail to {email_to:<30}", end="")
                server.sendmail(email_from, email_to, email_body)
                print("[OK]")
                time.sleep(1)
            else:
                print(email_body)

    except smtplib.SMTPException as ex:
        print(f"SMTP borked: {ex=}")

    finally:
        server.close()            


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--no-dry-run", action="store_true")
    parser.add_argument("--test-email", action="store_true")

    args = parser.parse_args()
    dry_run = not args.no_dry_run

    config, rules, participants = load_settings()

    max_attempts = 20
    attempts = 0

    if config["smtp"]["password"].startswith("$"):
        pass_var = config["smtp"]["password"][1:]

        try:
            config["smtp"]["password"] = os.environ[pass_var]
        except KeyError:
            if dry_run:
                config["smtp"]["password"] = ""
            else:
                print(f"Cannot continue. Env var {pass_var} not found.")
                exit(1)

    elif config["smtp"]["password"].startswith("\$"):
        config["smtp"]["password"] = config["smtp"]["password"][1:]


    if args.test_email:
        print("E-mail testing mode, sending one giver and one receiver e-mail to the configured test address...")
        send_emails(
            config, rules, [[
                {"name": f"{config['testing']['name']} (giver)",    "email": config["testing"]["email"]},
                {"name": f"{config['testing']['name']} (receiver)", "email": config["testing"]["email"]}
            ]], dry_run=False)

        print("Test e-mails sent")
    else:
        for _ in range(max_attempts):
            try:
                attempts = attempts + 1
                pairs = solve(participants)

                send_emails(config, rules, pairs, dry_run)

            except DeadEndException:
                print("Failed to solve, retrying...")
                continue
            else:
                break

        print("")
        print("Finished!")