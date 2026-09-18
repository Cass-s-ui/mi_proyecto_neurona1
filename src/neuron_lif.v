`default_nettype none

module neuron_lif (
    input  wire        clk,        // Reloj del sistema
    input  wire        rst_n,      // Reset global (Activo en bajo)
    input  wire [5:0]  stimulus,   // Estímulo de entrada sumado
    input  wire [3:0]  leak,       // Pérdida o fuga configurable
    input  wire [3:0]  threshold,  // Umbral dinámico de disparo
    output reg         spike       // Pulso de salida de la neurona
);

    // Registro del potencial de membrana de 8 bits
    reg [7:0] v_mem;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            v_mem <= 8'b0;
            spike <= 1'b0;
        end else begin
            // Si el potencial supera el umbral (escalado a 8 bits)
            if (v_mem >= {threshold, 4'b0000}) begin
                spike <= 1'b1;     // ¡Disparo de la neurona!
                v_mem <= 8'b0;     // Reseteo biológico del potencial
            end else begin
                spike <= 1'b0;     // No hay disparo
                
                // Sumamos estímulo y restamos la fuga de forma segura
                if ((v_mem + stimulus) > {leak, 4'b0000}) begin
                    v_mem <= (v_mem + stimulus) - {leak, 4'b0000};
                end else begin
                    v_mem <= 8'b0; // Protección contra valores negativos (underflow)
                end
            end
        end
    end

endmodule
