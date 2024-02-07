    ;; A simple watchdog timer module.
    ;;
    ;; Define `wdtcon_init` if you want to change the default.
    ;; Define WDT_RESET_EVENT if you want to handle WDT resets.

    ifdef       diosph_init
    ifdef       wdtcon_init
    movlw       wdtcon_init
    banksel     WDTCON
    movwf       WDTCON
    endif       ; wdtcon_init


    ifdef       WDT_RESET_EVENT
    pagesel     wdt_reset_end
    btfss       STATUS, NOT_TO
    goto        wdt_reset_end
    diospost    WDT_RESET_EVENT
wdt_reset_end:
    endif       ; WDT_RESET_EVENT
    endif       ; wdtcon_init


    ifdef   diosph_idle
    clrwdt
    endif   ; diosph_idle
