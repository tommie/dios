    ifdef   diosh_init
    ;; We don't change CONFIG1, so the WDT is enabled there.
    ;; But we lower the prescaler.
wdt_test_wdtcon_init    equ (0 << WDTPS0) | (1 << SWDTEN)

    movlw   0
    banksel PORTA
    movwf   PORTA
    movlw   ~1
    banksel TRISA
    movwf   TRISA
    endif   ; diosh_init

    ifdef   diosh_event_WDT_RESET_EVENT
    ;; This is a boring test: if PORTA stays cleared, the clrwdt works.
    banksel PORTA
    bsf     PORTA, 0
    endif   ; diosh_event_WDT_RESET_EVENT
