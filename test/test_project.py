import cocotb
from cocotb.triggers import RisingEdge, ClockCycles
from cocotb.clock import Clock


def read_weight(dut):
    return (dut.uo_out.value.to_unsigned() >> 1) & 0x3F


@cocotb.test()
async def test_neuron_learning(dut):
    """Prueba avanzada: Plasticidad STDP al extremo (Potenciacion y Depresion)"""

    # 1. Configurar un reloj del sistema de 50 MHz
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())

    # Parametros: Umbral=8, Fuga=1, Ventana STDP=7 (Máxima sensibilidad)
    window = 7
    config_bits = (window << 5) | (1 << 1)
    threshold_normal = 8

    # 2. Estado inicial: aplicamos la configuracion ANTES de liberar el reset.
    # (si se libera el reset con threshold=0 todavia sin configurar, la neurona
    # dispara sola en cada ciclo y contamina tau_post antes de que el test
    # arranque, causando depresion espuria mas adelante)
    dut._log.info("Iniciando el chip y aplicando Reset...")
    dut.ena.value = 1
    dut.rst_n.value = 0
    dut.ui_in.value = config_bits
    dut.uio_in.value = threshold_normal
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    weight_initial = read_weight(dut)
    dut._log.info(f"Peso sinaptico inicial: {weight_initial}")

    dut._log.info("--- FASE 1: FORZANDO POTENCIACIÓN MÁXIMA (LTP) ---")
    # Estimulamos con un duty cycle alto (2 ciclos con spike_pre en alto, 1 en
    # bajo) para que el estimulo acumulado supere la fuga y el potencial de
    # membrana realmente alcance el umbral y dispare spike_post. Tras cada
    # disparo esperamos mas que la ventana STDP para que tau_post decaiga a 0
    # antes de la siguiente rafaga, evitando que un tau_post residual dispare
    # depresion espuria durante la fase de potenciacion.
    async def pulse_until_spike(max_iters=30):
        # Se corta apenas se detecta el disparo: mantener spike_pre en alto
        # 1-2 ciclos de mas justo despues del disparo reactiva la condicion de
        # LTP/LTD de forma espuria en el siguiente flanco (spike_post viejo +
        # spike_pre todavia en alto), revirtiendo el incremento que se acaba
        # de aplicar.
        for _ in range(max_iters):
            dut.ui_in.value = config_bits | 0x01
            await RisingEdge(dut.clk)
            if bool(dut.uo_out.value.to_unsigned() & 0x1):
                return True
            await RisingEdge(dut.clk)
            if bool(dut.uo_out.value.to_unsigned() & 0x1):
                return True
            dut.ui_in.value = config_bits & ~0x01
            await RisingEdge(dut.clk)
            if bool(dut.uo_out.value.to_unsigned() & 0x1):
                return True
        return False

    for i in range(10):
        fired = await pulse_until_spike()
        assert fired, f"LTP pulso {i}: la neurona nunca alcanzo el umbral de disparo"
        dut._log.info(f"Pulso LTP {i} -> Peso Sinaptico actual: {read_weight(dut)}")
        # cooldown: deja decaer tau_post por completo antes de la siguiente rafaga
        dut.ui_in.value = config_bits
        await ClockCycles(dut.clk, window + 2)

    weight_after_ltp = read_weight(dut)
    dut._log.info(f"Peso sinaptico tras LTP: {weight_after_ltp}")
    assert weight_after_ltp > weight_initial, (
        f"LTP no potencio el peso: inicial={weight_initial}, tras LTP={weight_after_ltp}"
    )

    dut._log.info("--- FASE 2: FORZANDO DEPRESIÓN MÁXIMA (LTD) ---")
    # Forzamos un unico disparo post-sinaptico aislado (threshold=0 durante
    # exactamente 1 ciclo), restauramos el umbral normal, y recien entonces
    # aplicamos el pulso pre-sinaptico. Si dejaramos threshold=0 de forma
    # continua la neurona dispararia en cada ciclo, y la prioridad if/else de
    # stdp_core favorece potenciacion siempre que spike_post este activo,
    # causando el efecto contrario al buscado.
    for i in range(10):
        dut.uio_in.value = 0
        await RisingEdge(dut.clk)
        dut.uio_in.value = threshold_normal
        await RisingEdge(dut.clk)  # deja que se registre el spike_post aislado
        dut.ui_in.value = config_bits | 0x01  # spike_pre, con tau_post aun activo
        await RisingEdge(dut.clk)
        dut.ui_in.value = config_bits & ~0x01
        await RisingEdge(dut.clk)

        dut._log.info(f"Pulso LTD {i} -> Peso Sinaptico actual: {read_weight(dut)}")
        # cooldown: deja decaer tau_pre por completo antes del siguiente ciclo
        await ClockCycles(dut.clk, window + 2)

    weight_after_ltd = read_weight(dut)
    dut._log.info(f"Peso sinaptico tras LTD: {weight_after_ltd}")
    assert weight_after_ltd < weight_after_ltp, (
        f"LTD no deprimio el peso: tras LTP={weight_after_ltp}, tras LTD={weight_after_ltd}"
    )

    dut._log.info("Simulacion dinamica completada con exito.")
