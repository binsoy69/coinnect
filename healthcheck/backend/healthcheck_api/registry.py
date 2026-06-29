"""Fixed diagnostics component registry."""

from app.core.constants import BillDenom, CoinDenom

from healthcheck_api.models import ComponentGroup, TestDefinition

BILL_DENOMS = [
    BillDenom.PHP_20,
    BillDenom.PHP_50,
    BillDenom.PHP_100,
    BillDenom.PHP_200,
    BillDenom.PHP_500,
    BillDenom.PHP_1000,
    BillDenom.USD_10,
    BillDenom.USD_50,
    BillDenom.EUR_5,
    BillDenom.EUR_10,
]

COIN_DENOMS = [
    CoinDenom.PHP_1,
    CoinDenom.PHP_5,
    CoinDenom.PHP_10,
    CoinDenom.PHP_20,
]

CURRENCIES = ["PHP", "USD", "EUR"]


def build_component_groups() -> list[ComponentGroup]:
    """Return the complete command-level v1 diagnostics surface."""

    return [
        ComponentGroup(
            id="connectivity",
            label="Controller Connectivity",
            description="Serial protocol checks for both Arduino Mega controllers.",
            tests=[
                TestDefinition(
                    id="connectivity_bill_ping",
                    label="Bill Controller Ping",
                    component="Arduino Mega #1",
                    kind="connectivity",
                    description="Send PING to the bill controller.",
                ),
                TestDefinition(
                    id="connectivity_bill_version",
                    label="Bill Controller Version",
                    component="Arduino Mega #1",
                    kind="connectivity",
                    description="Read firmware version from the bill controller.",
                ),
                TestDefinition(
                    id="connectivity_coin_ping",
                    label="Coin/Security Ping",
                    component="Arduino Mega #2",
                    kind="connectivity",
                    description="Send PING to the coin/security controller.",
                ),
                TestDefinition(
                    id="connectivity_coin_version",
                    label="Coin/Security Version",
                    component="Arduino Mega #2",
                    kind="connectivity",
                    description="Read firmware version from the coin/security controller.",
                ),
            ],
        ),
        ComponentGroup(
            id="rpi_bill_acceptor",
            label="RPi Bill Acceptor",
            description="Raspberry Pi GPIO, lighting, conveyor, and camera checks.",
            tests=[
                TestDefinition(
                    id="rpi_ir_entry",
                    label="Read Entry IR",
                    component="GPIO5",
                    kind="sensor",
                    description="Read the bill entry IR sensor.",
                ),
                TestDefinition(
                    id="rpi_ir_position",
                    label="Read Position IR",
                    component="GPIO6",
                    kind="sensor",
                    description="Read the bill position IR sensor.",
                ),
                TestDefinition(
                    id="rpi_conveyor_forward",
                    label="Conveyor Forward",
                    component="Bill acceptor motor",
                    kind="actuator",
                    description="Run the conveyor forward for one second.",
                    caution="Moves the bill acceptor conveyor.",
                ),
                TestDefinition(
                    id="rpi_conveyor_reverse",
                    label="Conveyor Reverse",
                    component="Bill acceptor motor",
                    kind="actuator",
                    description="Run the conveyor in reverse for one second.",
                    caution="Moves the bill acceptor conveyor.",
                ),
                TestDefinition(
                    id="rpi_uv_led",
                    label="UV LED",
                    component="GPIO23",
                    kind="actuator",
                    description="Turn the UV LED on for one second.",
                    caution="Avoid looking directly at UV light.",
                ),
                TestDefinition(
                    id="rpi_white_led",
                    label="White LED",
                    component="GPIO24",
                    kind="actuator",
                    description="Turn the white LED on for one second.",
                ),
                TestDefinition(
                    id="rpi_camera_capture",
                    label="Camera Capture",
                    component="USB camera",
                    kind="camera",
                    description="Capture one frame from the bill authentication camera.",
                ),
            ],
        ),
        ComponentGroup(
            id="paperang_printer",
            label="Paperang Printer",
            description="Bluetooth receipt printer checks for the Paperang P1.",
            tests=[
                TestDefinition(
                    id="paperang_sample_receipt",
                    label="Print Sample Receipt",
                    component="Paperang P1",
                    kind="printer",
                    description="Print a small Coinnect sample receipt over Bluetooth.",
                    caution="Physically prints on the Paperang P1.",
                ),
            ],
        ),
        ComponentGroup(
            id="bill_ml_models",
            label="Bill ML Models",
            description="Validate configured YOLO model files and class labels.",
            tests=[
                TestDefinition(
                    id=f"bill_ml_models_{currency.lower()}",
                    label=f"{currency} Model Pair",
                    component=f"{currency} auth + denomination models",
                    kind="ml",
                    description=(
                        f"Load configured {currency} bill authentication and "
                        "denomination YOLO models and verify class labels."
                    ),
                )
                for currency in CURRENCIES
            ],
        ),
        ComponentGroup(
            id="bill_image_recognition",
            label="Bill Image Recognition",
            description="Live camera checks for bill authentication and denomination.",
            tests=[
                *[
                    TestDefinition(
                        id=f"bill_image_auth_{currency.lower()}",
                        label=f"{currency} Auth Image",
                        component="Camera + UV LED + auth model",
                        kind="ml",
                        description=(
                            f"Turn on UV light, capture a bill image, and run "
                            f"the {currency} authentication model."
                        ),
                        caution="Turns on UV light. Place a bill in camera view first.",
                    )
                    for currency in CURRENCIES
                ],
                *[
                    TestDefinition(
                        id=f"bill_image_denom_{currency.lower()}",
                        label=f"{currency} Denom Image",
                        component="Camera + white LED + denomination model",
                        kind="ml",
                        description=(
                            f"Turn on white light, capture a bill image, and run "
                            f"the {currency} denomination model."
                        ),
                    )
                    for currency in CURRENCIES
                ],
            ],
        ),
        ComponentGroup(
            id="bill_acceptor_full_flow",
            label="Bill Acceptor Full Flow",
            description="End-to-end physical bill intake, recognition, and storage.",
            tests=[
                TestDefinition(
                    id=f"bill_acceptor_flow_{currency.lower()}",
                    label=f"{currency} Bill Acceptor Flow",
                    component="Entry IR + timed conveyor + LEDs + ML + sorter",
                    kind="ml",
                    description=(
                        f"Wait for a {currency} bill at entry IR, run the "
                        "conveyor for the calibrated pull duration, authenticate "
                        "it, identify denomination, then sort and store."
                    ),
                    caution=(
                        "Moves the bill conveyor and sorter. Accepted genuine bills "
                        "are stored and inventory is incremented."
                    ),
                )
                for currency in CURRENCIES
            ],
        ),
        ComponentGroup(
            id="bill_controller",
            label="Bill Sorting and Dispensing",
            description="Sorter rail and bill dispenser command-level checks.",
            tests=[
                TestDefinition(
                    id="bill_home_sorter",
                    label="Home Sorter",
                    component="Sorter rail",
                    kind="actuator",
                    description="Run the sorter homing sequence.",
                    caution="Moves the bill sorting rail.",
                ),
                TestDefinition(
                    id="bill_sort_status",
                    label="Sorter Status",
                    component="Sorter rail",
                    kind="status",
                    description="Read current sorter position and homed state.",
                ),
                *[
                    TestDefinition(
                        id=f"bill_sort_{denom.value}",
                        label=f"Sort to {denom.value}",
                        component="Sorter rail",
                        kind="actuator",
                        description=f"Move sorter to the slot for {denom.value}.",
                        caution="Moves the bill sorting rail.",
                    )
                    for denom in BILL_DENOMS
                ],
                *[
                    TestDefinition(
                        id=f"bill_dispenser_status_{denom.value}",
                        label=f"{denom.value} Dispenser Status",
                        component=f"{denom.value} dispenser",
                        kind="status",
                        description=f"Check readiness for the {denom.value} dispenser.",
                    )
                    for denom in BILL_DENOMS
                ],
                *[
                    TestDefinition(
                        id=f"bill_dispense_{denom.value}",
                        label=f"Dispense 1 {denom.value}",
                        component=f"{denom.value} dispenser",
                        kind="actuator",
                        description=f"Dispense exactly one {denom.value} bill.",
                        caution="Physically releases one bill if loaded.",
                    )
                    for denom in BILL_DENOMS
                ],
                TestDefinition(
                    id="bill_conveyor_php",
                    label="PHP Dispense Conveyor",
                    component="PHP Dispense Conveyor Motor",
                    kind="actuator",
                    description="Run the PHP dispense conveyor motor for one second.",
                    caution="Moves the PHP dispense conveyor.",
                ),
                TestDefinition(
                    id="bill_conveyor_foreign",
                    label="Foreign Dispense Conveyor",
                    component="Foreign Dispense Conveyor Motor",
                    kind="actuator",
                    description="Run the Foreign dispense conveyor motor for one second.",
                    caution="Moves the Foreign dispense conveyor.",
                ),
            ],
        ),
        ComponentGroup(
            id="coin_security",
            label="Coin and Security",
            description="Coin dispenser, coin acceptor, lock, and tamper checks.",
            tests=[
                TestDefinition(
                    id="coin_security_status",
                    label="Security Status",
                    component="Security controller",
                    kind="status",
                    description="Read lock and tamper state.",
                ),
                TestDefinition(
                    id="coin_security_lock",
                    label="Lock Door",
                    component="Solenoid lock",
                    kind="actuator",
                    description="Engage the solenoid lock.",
                    caution="Locks the maintenance door.",
                ),
                TestDefinition(
                    id="coin_security_unlock",
                    label="Unlock Door",
                    component="Solenoid lock",
                    kind="actuator",
                    description="Disengage the solenoid lock.",
                    caution="Unlocks the maintenance door.",
                ),
                TestDefinition(
                    id="coin_reset",
                    label="Reset Coin Counter",
                    component="Coin acceptor",
                    kind="status",
                    description="Reset the Arduino coin accumulator to zero.",
                ),
                TestDefinition(
                    id="coin_status",
                    label="Coin Status",
                    component="Coin acceptor + sorter",
                    kind="status",
                    description="Read acceptor enable state, sorter position, and session total.",
                ),
                TestDefinition(
                    id="coin_acceptor_enable_on",
                    label="Enable Coin Acceptor",
                    component="Coin acceptor enable pin D24",
                    kind="actuator",
                    description="Drive the active-HIGH coin acceptor enable pin on.",
                    caution="Allows the coin acceptor to accept inserted coins.",
                ),
                TestDefinition(
                    id="coin_acceptor_enable_off",
                    label="Disable Coin Acceptor",
                    component="Coin acceptor enable pin D24",
                    kind="actuator",
                    description="Drive the active-HIGH coin acceptor enable pin off.",
                ),
                TestDefinition(
                    id="coin_sorter_center",
                    label="Sorter Center",
                    component="Coin sorter servo D7",
                    kind="actuator",
                    description="Move the coin sorter servo to CENTER at 81 degrees.",
                    caution="Moves the coin sorter servo.",
                ),
                TestDefinition(
                    id="coin_sorter_left",
                    label="Sorter Left",
                    component="Coin sorter servo D7",
                    kind="actuator",
                    description="Move the coin sorter servo to LEFT at 45 degrees.",
                    caution="Moves the coin sorter servo.",
                ),
                TestDefinition(
                    id="coin_sorter_right",
                    label="Sorter Right",
                    component="Coin sorter servo D7",
                    kind="actuator",
                    description="Move the coin sorter servo to RIGHT at 120 degrees.",
                    caution="Moves the coin sorter servo.",
                ),
                *[
                    TestDefinition(
                        id=f"coin_dispense_{denom.value}",
                        label=f"Dispense 1 PHP_{denom.value}",
                        component=f"PHP_{denom.value} coin servo",
                        kind="actuator",
                        description=f"Dispense exactly one PHP_{denom.value} coin.",
                        caution="Physically releases one coin if loaded.",
                    )
                    for denom in COIN_DENOMS
                ],
                TestDefinition(
                    id="coin_acceptor_listen",
                    label="Listen for Coin",
                    component="Coin acceptor",
                    kind="sensor",
                    description="Wait up to 10 seconds for a COIN_IN event.",
                ),
                TestDefinition(
                    id="coin_tamper_listen",
                    label="Listen for Tamper",
                    component="Shock sensors",
                    kind="sensor",
                    description="Wait up to 10 seconds for a TAMPER event.",
                ),
                TestDefinition(
                    id="coin_rfid_listen",
                    label="Listen for RFID Scan",
                    component="MFRC522 RFID reader",
                    kind="sensor",
                    description="Wait up to 10 seconds for an RFID card to be swiped.",
                ),
            ],
        ),
    ]


def flatten_tests(groups: list[ComponentGroup]) -> dict[str, TestDefinition]:
    return {test.id: test for group in groups for test in group.tests}
