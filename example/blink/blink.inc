    ifdef           diosh_defs
LED_BIT             equ 0
blink_trisa_init    equ ~(1 << LED_BIT)
    endif           ; diosh_defs


    ifdef   diosh_event_IDLE_QUEUE_BLINK_EVENT
    movlw   (1 << LED_BIT)
    banksel PORTA
    xorwf   PORTA, F
    endif   ; diosh_event_IDLE_QUEUE_BLINK_EVENT
