// import { UserRepositoryInterface } from "./user.repository.interface";
// import { AppDataSource } from "../config/ormconfig";
// import { User } from "../entities/wstmngMeta.entity";
// import { UserInterface } from "../interfaces/index";
// import logger from "../config/logger";

// const userDataSource = AppDataSource.getRepository(User);

// export class UserRepository implements UserRepositoryInterface {

//     constructor() {}

//     async save(user: User) {
//         return await userDataSource.save(user);
//     }

//     async delete(user: User) {
//         const result = await userDataSource.delete(user.id);
//         logger.debug(JSON.stringify(result));
//         return;
//     }
// // 
//     async deleteById(userId: string) {
//         const result = await userDataSource.delete(userId);
//         logger.debug(JSON.stringify(result));
//         return;
//     }

//     async findById(id: string) {
//         // const userRepository = AppDataSource.getRepository(User);
//         // return await userDataSource.findOne({where: {id: id}});
//         return await userDataSource.findOneBy({ id });
//     }

//     async findByEmail(email: string) {
//         return await userDataSource.findOneBy({ email });
//     }

//     async findByUsername(username: string) {
//         return await userDataSource.findOneBy({ username });
//     }

//     async existsByUsername(username: string) {
//         return await userDataSource.existsBy({ username });
//     }
// }