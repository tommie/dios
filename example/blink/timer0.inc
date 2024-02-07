    ifdef           diosh_defs
                    ;; 1:32 prescaler assigned to TMR0.
timer0_option_init  equ ~((1 << T0CS) | (1 << PSA) | (3 << PS0))
timer0_intcon_init  equ 1 << T0IE
    endif           ; diosh_defs


    ifdef       diosh_irq_timer0
    diospost    BLINK_EVENT
    endif       ; diosh_irq_timer0
