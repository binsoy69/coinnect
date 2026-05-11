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
    BillDenom.USD_100,
    BillDenom.EUR_5,
    BillDenom.EUR_10,
    BillDenom.EUR_20,
]

COIN_DENOMS = [
    CoinDenom.PHP_1,
    CoinDenom.PHP_5,
    CoinDenom.PHP_10,
    CoinDenom.PHP_20,
]


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
                    description="Read the camera-position IR sensor.",
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
            ],
        ),
    ]


def flatten_tests(groups: list[ComponentGroup]) -> dict[str, TestDefinition]:
    return {test.id: test for group in groups for test in group.tests}
