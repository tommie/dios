timer0_option_init  equ ~((1 << T0CS) | (1 << PSA))
timer0_intcon_init  equ 1 << T0IE

    ifdef       diosh_irq_t0
    diospost    BLINK_EVENT
    endif       ; diosh_irq_timer0
