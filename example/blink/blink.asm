    dios

    include "p16f887.inc"

    module  "timer0.inc"
    module  "blink.inc"
    module  "init.inc"

    const   option_init, and    ; The default is 0xFF.
    const   intcon_init, or     ; The default is 0.
    const   trisa_init, and     ; The default is 0xFF.
    const   porta_init, or      ; The default is 0.

    irq     irq_timer0, INTCON, T0IF

    evqueue IDLE_QUEUE, idle
    event   BLINK_EVENT
