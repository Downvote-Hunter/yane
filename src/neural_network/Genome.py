import random
from copy import deepcopy

import numpy as np

from src.neural_network import YaneConfig
from src.neural_network.Connection import Connection
from src.neural_network.NeuralNetwork import NeuralNetwork
from src.neural_network.Node import Node
from src.neural_network.NodeTypes import NodeTypes
from src.neural_network.exceptions.InvalidConnection import InvalidConnection

yane_config = YaneConfig.load_json_config()


class Genome:
    def __init__(self, node_genes=None):
        self.bad_reproduction_count = 0
        self.brain: NeuralNetwork = NeuralNetwork()
        self.parent: Genome | None = None
        self.fitness = None
        self.net_cost = None
        self.reproduction_count = 0

        # Mutation probability
        self.mutation_enabled_probability = 0.1  # probability of enabling / disabling connection
        self.mutation_activation_function_probability = 0.1  # probability of mutating activation function
        self.mutation_add_connection_probability = 0.1  # probability of adding connection
        self.mutation_remove_connection_probability = 0.1  # probability of removing connection
        self.mutation_add_node_probability = 0.1  # probability of adding node
        self.mutation_remove_node_probability = 0.1  # probability of removing node
        self.mutation_mutation_probability = 0.8  # probability of mutating a mutation

        if node_genes is not None:
            for node in node_genes:
                self.add_node(node)

    @classmethod
    def crossover_connections(cls, genome1, genome2):
        connection_genes1 = genome1.get_brain().get_all_connections()
        connection_genes2 = genome2.get_brain().get_all_connections()

        return Genome.crossover_genes(connection_genes1, connection_genes2)

    @classmethod
    def align_gene_ids(cls, genes1, genes2):
        aligned_genes = []

        index1 = 0
        index2 = 0

        while index1 < len(genes1) and index2 < len(genes2):
            node1 = genes1[index1]
            node2 = genes2[index2]

            if node1.get_id() == node2.get_id():
                aligned_genes.append((node1, node2))
                index1 += 1
                index2 += 1
            elif node1.get_id() < node2.get_id():
                aligned_genes.append((node1, None))
                index1 += 1
            elif node1.get_id() > node2.get_id():
                aligned_genes.append((None, node2))
                index2 += 1

        while index1 < len(genes1):
            aligned_genes.append((genes1[index1], None))
            index1 += 1

        while index2 < len(genes2):
            aligned_genes.append((None, genes2[index2]))
            index2 += 1

        return aligned_genes

    @classmethod
    def crossover_genes(cls, gene1, gene2) -> list:
        aligned_genes = Genome.align_gene_ids(gene1, gene2)

        new_genes = []

        for gene1, gene2 in aligned_genes:
            if gene1 is None:
                new_genes.append(gene2)
            elif gene2 is None:
                new_genes.append(gene1)
            else:
                if random.random() < 0.5:
                    new_genes.append(gene1)
                else:
                    new_genes.append(gene2)

        return deepcopy(new_genes)

    @classmethod
    def crossover_nodes(cls, genome1, genome2) -> list:
        node_genes1 = genome1.get_brain().get_all_nodes()
        node_genes2 = genome2.get_brain().get_all_nodes()

        return Genome.crossover_genes(node_genes1, node_genes2)

    @classmethod
    def crossover(cls, genome1, genome2) -> 'Genome':
        node_genes = Genome.crossover_nodes(genome1, genome2)
        child_genome = Genome(node_genes)

        return child_genome

    def get_brain(self):
        return self.brain

    def get_fitness(self):
        return self.fitness

    def set_fitness(self, fitness):
        self.fitness = fitness

    def get_net_cost(self):
        return self.net_cost

    def set_net_cost(self, net_cost):
        self.net_cost = net_cost

    # callback_evaluator is a function that takes a genome as a parameter and returns a fitness value
    # This function is used to evaluate the fitness of a genome
    # You have to implement this function yourself since it is specific to your problem
    def evaluate(self, callback_evaluator):
        self.set_net_cost(self.get_brain().calculate_net_cost())

        fitness_result = callback_evaluator(self)

        self.clear_hidden_output_nodes()

        # net_cost = self.get_net_cost()

        if self.parent is not None and fitness_result >= self.parent.get_fitness():
            self.parent.set_bad_reproduction_count(0)

        # Child genome is worse than parent genome
        if self.parent is not None and fitness_result < self.parent.get_fitness():
            parent_connection = self.get_parent().get_brain().get_last_weight_shift_connection()
            self.parent.set_bad_reproduction_count(self.parent.get_bad_reproduction_count() + 1)
            if parent_connection is not None:
                parent_connection.switch_weight_shift_direction()

        # TODO: Remove net cost as soon as fitness prioritization is implemented
        # self.set_fitness(fitness_result - net_cost * YaneConfig.get_net_cost_factor(yane_config))
        self.set_fitness(fitness_result)
        return self.get_fitness()

    # Avoid deep copy because of recursion
    def copy(self):
        new_genome = Genome()

        for node in self.get_brain().get_all_nodes():
            new_genome.add_node(node.copy())

        for connection in self.get_brain().get_all_connections():
            new_connection = connection.copy()
            new_connection.set_in_node(new_genome.get_brain().get_node_by_id(connection.get_in_node().get_id()))
            new_connection.set_out_node(new_genome.get_brain().get_node_by_id(connection.get_out_node().get_id()))
            new_genome.add_connection(new_connection)

        return new_genome

    def add_node(self, node: Node):
        self.brain.add_node(node)

    def mutate(self):
        self.mutate_nodes()
        self.mutate_connections()
        self.mutate_mutations()

    def mutate_nodes(self):
        nodes = self.get_hidden_nodes() + self.get_output_nodes()

        for node in nodes:
            if random.random() < self.mutation_activation_function_probability:
                node.mutate_activation_function()

        if random.random() < self.mutation_add_node_probability:
            self.add_random_node()
        if random.random() < self.mutation_remove_node_probability:
            self.remove_random_node()

    def add_random_node(self):

        if len(self.get_all_connections()) <= 0:
            return None

        connection = random.choice(self.get_all_connections())
        node_in: Node = connection.get_in_node()

        new_node = Node(NodeTypes.HIDDEN)
        new_connection = Connection()

        self.add_node(new_node)

        # A ---> C
        # A ---> B ---> C

        new_connection.set_in_node(node_in)
        new_connection.set_out_node(new_node)
        connection.set_in_node(new_node)
        node_in.remove_next_connection(connection)
        new_node.add_next_connection(connection)
        new_connection.set_weight(1.0)

        self.add_connection(new_connection)

        return new_node

    def remove_random_node(self):
        nodes = self.get_hidden_nodes()

        if len(nodes) > 0:
            node = random.choice(nodes)
            self.remove_node(node)

    def remove_node(self, remove_node):
        if remove_node in self.brain.input_nodes:
            self.brain.input_nodes.remove(remove_node)
        elif remove_node in self.brain.hidden_nodes:
            self.brain.hidden_nodes.remove(remove_node)
        elif remove_node in self.brain.output_nodes:
            self.brain.output_nodes.remove(remove_node)

        for node in self.get_all_nodes():
            for con in node.get_next_connections():
                if con.get_out_node() == remove_node:
                    node.remove_next_connection(con)

    def mutate_connections(self):
        connections = self.get_all_connections()

        if len(connections) <= 0:
            self.add_random_connection()
            return

        for connection in connections:
            if random.random() < YaneConfig.get_mutation_weight_probability(yane_config):
                connection.mutate_weight_random()
            if random.random() < self.mutation_enabled_probability:
                connection.mutate_enabled()
            if random.random() < YaneConfig.get_mutation_shift_probability(yane_config):
                self.brain.last_weight_shift_connection = connection.mutate_weight_shift()
            if random.random() < self.mutation_add_connection_probability:
                self.add_random_connection()
            if random.random() < self.mutation_remove_connection_probability:
                self.remove_random_connection()

    def remove_random_connection(self):
        connections = self.get_all_connections()

        if len(connections) > 0:
            connection = random.choice(connections)
            self.remove_connection(connection)

    def remove_connection(self, remove_connection):
        if remove_connection in self.get_all_connections():
            remove_connection.get_in_node().remove_next_connection(remove_connection)

    def add_random_connection(self):
        random_node_in: Node = self.get_random_node()
        random_node_out: Node = self.get_random_node()

        connection = Connection()
        connection.set_in_node(random_node_in)
        connection.set_out_node(random_node_out)
        connection.set_weight(YaneConfig.get_random_mutation_weight(yane_config))

        try:
            self.add_connection(connection)
        except InvalidConnection:
            pass

    def print(self):
        print("Genome: " + str(self.get_fitness()) + " with net cost: " + str(self.get_net_cost()) + " and " + str(
            len(self.get_brain().get_forward_order_list())) + " connected nodes")

        print("Mutation probabilities: \n" + "Mutation connection enabled / disabled: " + str(
            self.mutation_enabled_probability) + "\nMutation activation: " + str(
            self.mutation_activation_function_probability) + "\nMutation mutation: " + str(
            self.mutation_mutation_probability) + "\nMutation add connection: " + str(
            self.mutation_add_connection_probability) + "\nMutation remove connection: " + str(
            self.mutation_remove_connection_probability) + "\n")

        self.brain.print()

    def get_all_nodes(self):
        return self.brain.get_all_nodes()

    def add_connection(self, connection):
        self.brain.add_connection(connection)

    def set_input_data(self, data):
        self.brain.set_input_data(data)

    def forward_propagation(self, data=None):
        self.brain.forward_propagation(data)

    def get_outputs(self) -> list:
        return self.brain.get_output_data()

    def set_number_of_outputs(self, number_of_outputs):
        for i in range(number_of_outputs):
            output_node = Node(NodeTypes.OUTPUT)
            self.add_node(output_node)

    def set_parent(self, parent: 'Genome'):
        self.parent = parent

    def get_reproduction_count(self):
        return self.reproduction_count

    def set_reproduction_count(self, reproduction_count):
        self.reproduction_count = reproduction_count

    # smaller is better
    def get_species_compatibility(self, genome):

        node_difference = 0
        connection_difference = 0
        weight_difference = np.abs(self.get_average_weight() - genome.get_average_weight())

        aligned_nodes = Genome.align_gene_ids(self.get_brain().get_all_nodes(),
                                              genome.get_brain().get_all_nodes())
        aligned_connections = Genome.align_gene_ids(self.get_brain().get_all_connections(),
                                                    genome.get_brain().get_all_connections())

        for node1, node2 in aligned_nodes:
            if node1 is None or node2 is None:
                node_difference += 1

        for connection1, connection2 in aligned_connections:
            if connection1 is None or connection2 is None:
                connection_difference += 1

        return YaneConfig.get_species_compatibility_node_factor(yane_config) * node_difference + \
            YaneConfig.get_species_compatibility_connection_factor(yane_config) * connection_difference + \
            YaneConfig.get_species_compatibility_weight_factor(yane_config) * weight_difference

    def get_average_weight(self):

        sum_weight = 0

        if len(self.brain.get_all_connections()) == 0:
            return 0

        for connection in self.brain.get_all_connections():
            sum_weight += connection.get_weight()

        return sum_weight / len(self.brain.get_all_connections())

    def clear_hidden_output_nodes(self):
        for node in self.brain.get_hidden_nodes() + self.brain.get_output_nodes():
            node.set_value(0)

    def get_parent(self):
        return self.parent

    def set_bad_reproduction_count(self, value):
        self.bad_reproduction_count = value

    def get_bad_reproduction_count(self):
        return self.bad_reproduction_count

    def get_hidden_nodes(self):
        return self.brain.get_hidden_nodes()

    def get_output_nodes(self):
        return self.brain.get_output_nodes()

    def get_all_connections(self):
        return self.brain.get_all_connections()

    def get_random_node(self):
        return self.brain.get_random_node()

    def mutate_mutations(self):
        if random.random() < self.mutation_mutation_probability:
            self.mutation_enabled_probability = random.random()
        if random.random() < self.mutation_mutation_probability:
            self.mutation_activation_function_probability = random.random()
        if random.random() < self.mutation_mutation_probability:
            self.mutation_mutation_probability = random.random()
            if self.mutation_mutation_probability <= 0:
                self.mutation_mutation_probability = 0.01
        if random.random() < self.mutation_mutation_probability:
            self.mutation_add_connection_probability = random.random()
        if random.random() < self.mutation_mutation_probability:
            self.mutation_remove_connection_probability = random.random()
        if random.random() < self.mutation_mutation_probability:
            self.mutation_add_node_probability = random.random()
        if random.random() < self.mutation_mutation_probability:
            self.mutation_remove_node_probability = random.random()
