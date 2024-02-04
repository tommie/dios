    ifdef   diosh_init
    movlw   option_init
    banksel OPTION_REG
    movwf   OPTION_REG

    ;; In a larger program, these would be handled by
    ;; a separate port driver module.
    movlw   porta_init
    banksel PORTA
    movwf   PORTA
    movlw   trisa_init
    banksel TRISA
    movwf   TRISA

    movlw   (intcon_init) | (1 << GIE)
    banksel INTCON
    movwf   INTCON
    endif   ; diosh_init
