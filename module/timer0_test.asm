    dios

    module  "timer0.inc"
    module  "timer0_test.inc"

    irq     irq_timer0, INTCON, T0IF

    evqueue IDLE_QUEUE, idle
    event   TIMER0
    event   TIMER1
    event   TIMER2
    event   TIMER0_BAD_FUZZ_EVENT
