import json
import logging
import boto3
import random
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

logger = logging.getLogger()
try:
    log_level = os.environ["LogLevel"]
    if log_level not in ["INFO", "DEBUG"]:
        log_level = "INFO"
except BaseException:
    log_level = "INFO"
logger.setLevel(log_level)

dynamodb = boto3.resource('dynamodb')

def send_email(email):
    SENDER = 'HERE_GOES_YOUR_EMAIL@MAIL.com'
    RECIPIENT = email
    AWS_REGION = 'CHANGE_REGION'
    BODY_HTML = """<html>
        <head></head>
        <body>
        <h1>Cubierta de Poliza</h1>
        <p> Saludos, le compartimos su cubierta de poliza tal como solicitado.<br> <br>
        Gracias, <br>
        Powered by <br>
        </p>
        </body>
        </html>
    """

    CHARSET = "UTF-8"
    client = boto3.client('ses',region_name=AWS_REGION)
    
    try:
        #Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {'Charset': CHARSET, 'Data': BODY_HTML,},
                    'Text': { 'Charset': CHARSET, 'Data': "", },
                },
                'Subject': {
                'Charset': CHARSET,
                'Data': 'Triple S - Cubierta de Poliza',
                },
            },
            Source=SENDER,
        )

    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])
        
    #return response

def RouteCall(intent_request):
    session_attributes = get_session_attributes(intent_request)
    print(session_attributes)
    slots = get_slots(intent_request)
    slot = get_slot(intent_request, "email")
    emailResponse = get_email(slot)
    emailLength = len(emailResponse)
    
    if emailLength != 0:
        text = "Muchas gracias la confirmación. La solicitud ha sido procesada, su cubierta de poliza ha sido enviada a su correo electrónico. Muchas gracias por contactarnos."
        message = {"contentType": "PlainText", "content": text}
        fulfillment_state = "Fulfilled"
        send_email(emailResponse)
        return close(session_attributes, "CubiertaPoliza", fulfillment_state, message)
    else:
        print("No email found")
        if 'failure_count' in session_attributes:
            print(f"Failure Count: {session_attributes['failure_count']}")
            if int(session_attributes['failure_count']) >= 2:
                text = "Lo siento, no reconozco ese correo electrónico. Te contecto con un operador."
                message = {"contentType": "PlainText", "content": text}
                fulfillment_state = "Fulfilled"
                return close(session_attributes, "CubiertaPoliza", fulfillment_state, message)
            else:
                session_attributes['failure_count'] = int(session_attributes['failure_count']) + 1
                try_ex(lambda: slots.pop("email"))
                text = "Lo siento, no reconozco ese correo electrónico. Intenta nuevamente."
                message = {"contentType": "PlainText", "content": text}
                return elicit_slot(session_attributes, intent_request["sessionState"]["intent"]["name"], slots, "email", message)
        else:
            session_attributes['failure_count'] = 1
            try_ex(lambda: slots.pop("email"))
            text = "Lo siento, no reconozco ese correo electrónico. Intenta nuevamente."
            message = {"contentType": "PlainText", "content": text}
            return elicit_slot(session_attributes, intent_request["sessionState"]["intent"]["name"], slots, "email", message)


def FallbackIntent(intent_request):
    session_attributes = get_session_attributes(intent_request)
    slots = get_slots(intent_request)
    if 'failure_count' in session_attributes:
        if int(session_attributes['failure_count']) > 2:
            message = {"contentType": "PlainText", "content": text}
            text = "Lo sentimos, no logro entender su solicitud. Te voy a conectar con un agente de servicio."
            fulfillment_state = "Fulfilled"
            return close(session_attributes, "RouteCall", fulfillment_state, message)
        else:
            session_attributes['failure_count'] = int(session_attributes['failure_count']) + 1
            try_ex(lambda: slots.pop("Department"))
            text = "Lo siento, no logro entender su solicitud. Puedes intentar nuevamente?"
            message = {"contentType": "PlainText", "content": text}
            return elicit_slot(session_attributes, "RouteCall", slots, "Department", message)
    else:
        session_attributes['failure_count'] = 1
        try_ex(lambda: slots.pop("Department"))
        text = "Lo siento, no logro entender su solicitud. Puedes intentar nuevamente?"
        message = {"contentType": "PlainText", "content": text}
        return elicit_slot(session_attributes, "RouteCall", slots, "Department", message)


def dispatch(intent_request):
    intent_name = intent_request["sessionState"]["intent"]["name"]
    response = None
    # Dispatch to your bot's intent handlers
    if intent_name == "CubiertaPoliza":
        return RouteCall(intent_request)
    if intent_name == 'FallbackIntent':
        return FallbackIntent(intent_request)

    raise Exception("Esa acción aún no está en nuestro sistemas.")

def get_session_attributes(intent_request):
    sessionState = intent_request["sessionState"]
    if "sessionAttributes" in sessionState:
        return sessionState["sessionAttributes"]

    return {}

def get_email(email):
    try:
        table = dynamodb.Table('DOCUMENTS')

        response = table.query(
            IndexName='email-index',
            KeyConditionExpression=Key('email').eq(email)
        )
        
        #item = json.dumps(response['Items'])
        #contracts = json.loads(item)
        #contractNumber = contracts['Item']['customer_contract']['N']
        emailRecord = response['Items'][0]['email']
        print('EmailSlot: '+email)
        print('EmailRecord: '+emailRecord)
         
        if email == emailRecord:
            print('email found')
            return emailRecord
        else:
            print('email not found')
            return ""
    except Exception as err:
        logger.error("DynamoDB Query error: failed to fetch data from table. Error: ", exc_info=err)
        return ""


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.
    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None

def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        "messages": [message],
        "sessionState": {
            "sessionAttributes": session_attributes,
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_to_elicit},
            "intent": {"name": intent_name, "slots": slots},
        },
    }


def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        "messages": [message],
        "sessionState": {
            "sessionAttributes": session_attributes,
            "dialogAction": {"type": "ConfirmIntent"},
            "intent": {"name": intent_name, "slots": slots},
        },
    }

def close(session_attributes, intent_name, fulfillment_state, message):
    response = {
        "messages": [message],
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "sessionAttributes": session_attributes,
            "intent": {"name": intent_name, "state": fulfillment_state},
        },
    }

    return response

def get_slot(intent_request, slotName):
    slots = get_slots(intent_request)
    if slots is not None and slotName in slots and slots[slotName] is not None:
        if 'interpretedValue' in slots[slotName]['value']:
            return slots[slotName]["value"]["interpretedValue"]
        else:
            return None
    else:
        return None

def get_slots(intent_request):
    return intent_request["sessionState"]["intent"]["slots"]

def lambda_handler(event, context):
    print(event)
    response = dispatch(event)
    print(response)
    return response
