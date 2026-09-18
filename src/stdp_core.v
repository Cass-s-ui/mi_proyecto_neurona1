`default_nettype none

module stdp_core (
    input  wire        clk,          // Reloj global
    input  wire        rst_n,        // Reset global
    input  wire        spike_pre,    // Disparo de la neurona de entrada
    input  wire        spike_post,   // Disparo de nuestra neurona local (output)
    input  wire [3:0]  window_size,  // Tamaño de la ventana de tiempo programable
    output reg  [5:0]  weight        // El peso de la conexión corregido (salida)
);

    // Temporizadores internos para medir distancias de tiempo entre disparos
    reg [3:0] tau_pre;
    reg [3:0] tau_post;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tau_pre  <= 4'b0;
            tau_post <= 4'b0;
            weight   <= 6'd32; // Iniciamos a mitad de fuerza (32 de 63)
        end else begin
            // Si hay disparo previo, recargamos el contador de tiempo de entrada
            if (spike_pre) 
                tau_pre <= window_size;
            else if (tau_pre > 0) 
                tau_pre <= tau_pre - 1'b1; // El tiempo corre hacia atrás

            // Si hay disparo posterior, recargamos el contador de salida
            if (spike_post) 
                tau_post <= window_size;
            else if (tau_post > 0) 
                tau_post <= tau_post - 1'b1;

            // Regla STDP pura implementada a nivel de compuertas:
            if (spike_post && (tau_pre > 0)) begin
                // Potenciación (LTP): Si la entrada causó la salida, la conexión se fortalece
                if (weight < 6'd63) weight <= weight + 1'b1;
            end else if (spike_pre && (tau_post > 0)) begin
                // Depresión (LTD): Si la neurona disparó antes de que llegue la entrada, se debilita
                if (weight > 6'd0)  weight <= weight - 1'b1;
            end
        end
    end

endmodule
