import json
import typing
from datetime import timedelta
from nostr_sdk import Filter, Client, Alphabet, EventId, Event, PublicKey, Tag, Keys, nip04_decrypt, EventBuilder


def get_event_by_id(event_id: str, client: Client, config=None) -> Event | None:
    split = event_id.split(":")
    if len(split) == 3:
        pk = PublicKey.from_hex(split[1])
        id_filter = Filter().author(pk).custom_tag(Alphabet.D, [split[2]])
        events = client.get_events_of([id_filter], timedelta(seconds=config.RELAY_TIMEOUT))
    else:
        if str(event_id).startswith('note'):
            event_id = EventId.from_bech32(event_id)
        else:
            event_id = EventId.from_hex(event_id)

        id_filter = Filter().id(event_id).limit(1)
        events = client.get_events_of([id_filter], timedelta(seconds=config.RELAY_TIMEOUT))
    if len(events) > 0:
        return events[0]
    else:
        return None


def get_referenced_event_by_id(event_id, client, dvm_config, kinds) -> Event | None:
    if kinds is None:
        kinds = []

    if len(kinds) > 0:
        job_id_filter = Filter().kinds(kinds).event(EventId.from_hex(event_id)).limit(1)
    else:
        job_id_filter = Filter().event(EventId.from_hex(event_id)).limit(1)

    events = client.get_events_of([job_id_filter], timedelta(seconds=dvm_config.RELAY_TIMEOUT))

    if len(events) > 0:
        return events[0]
    else:
        return None


def send_event(event: Event, client: Client, dvm_config) -> EventId:
    relays = []

    for tag in event.tags():
        if tag.as_vec()[0] == 'relays':
            relays = tag.as_vec()[1].split(',')

    for relay in relays:
        if relay not in dvm_config.RELAY_LIST:
            client.add_relay(relay)

    event_id = client.send_event(event)

    for relay in relays:
        if relay not in dvm_config.RELAY_LIST:
            client.remove_relay(relay)

    return event_id


def check_and_decrypt_tags(event, dvm_config):
    try:
        tags = []
        is_encrypted = False
        p = ""
        sender = event.pubkey()
        for tag in event.tags():
            if tag.as_vec()[0] == 'encrypted':
                is_encrypted = True
            elif tag.as_vec()[0] == 'p':
                p = tag.as_vec()[1]

        if is_encrypted:
            if p != Keys.from_sk_str(dvm_config.PRIVATE_KEY).public_key().to_hex():
                print("[" + dvm_config.NIP89.name + "] Task encrypted and not addressed to this DVM, "
                                                    "skipping..")
                return None

            elif p == Keys.from_sk_str(dvm_config.PRIVATE_KEY).public_key().to_hex():
                print("encrypted")
                #encrypted_tag = Tag.parse(["encrypted"])
                #p_tag = Tag.parse(["p", p])

                tags_str = nip04_decrypt(Keys.from_sk_str(dvm_config.PRIVATE_KEY).secret_key(),
                                         event.pubkey(), event.content())
                #TODO add outer p tag so it doesnt have to be sent twice
                params = json.loads(tags_str)
                eventasjson = json.loads(event.as_json())
                eventasjson['tags'] = params
                eventasjson['content'] = ""
                event = Event.from_json(json.dumps(eventasjson))
                print(event.as_json())
    except Exception as e:
        print(e)

    return event
